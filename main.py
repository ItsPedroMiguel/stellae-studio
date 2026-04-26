import streamlit as st
import pymysql
import pandas as pd
from datetime import datetime
from datetime import datetime, timezone


# =========================
# CONFIGURAÇÃO DA BASE DE DADOS
# =========================

DB_CONFIG = {
    "host": st.secrets["database"]["host"],
    "user": st.secrets["database"]["user"],
    "password": st.secrets["database"]["password"],
    "database": st.secrets["database"]["database"],
    "charset": st.secrets["database"]["charset"],
    "cursorclass": pymysql.cursors.DictCursor,
}


# =========================
# LIGAÇÃO À BASE DE DADOS
# =========================

def get_connection():
    return pymysql.connect(**DB_CONFIG)


# =========================
# FORMATAR TIMESTAMP YITH
# =========================

def format_timestamp(value):
    if not value:
        return "-"

    try:
        return datetime.fromtimestamp(int(value)).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return value


# =========================
# PROCURAR CLIENTE
# =========================

def get_customer(search):
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            query = """
            SELECT 
                u.ID,
                u.user_email,

                MAX(CASE WHEN um.meta_key = 'first_name' THEN um.meta_value END) AS first_name,
                MAX(CASE WHEN um.meta_key = 'last_name' THEN um.meta_value END) AS last_name,
                MAX(CASE WHEN um.meta_key = 'billing_phone' THEN um.meta_value END) AS phone,
                MAX(CASE WHEN um.meta_key = 'data_nascimento' THEN um.meta_value END) AS birth_date,

                MAX(CASE WHEN um.meta_key = 'nome_encarregado_educacao' THEN um.meta_value END) AS encarregado,
                MAX(CASE WHEN um.meta_key = 'problema_saude' THEN um.meta_value END) AS problema_saude,

                MAX(CASE WHEN um.meta_key = 'billing_company' THEN um.meta_value END) AS company,
                MAX(CASE WHEN um.meta_key = 'billing_address_1' THEN um.meta_value END) AS address1,
                MAX(CASE WHEN um.meta_key = 'billing_address_2' THEN um.meta_value END) AS address2,
                MAX(CASE WHEN um.meta_key = 'billing_city' THEN um.meta_value END) AS city,
                MAX(CASE WHEN um.meta_key = 'billing_postcode' THEN um.meta_value END) AS postcode,
                MAX(CASE WHEN um.meta_key = 'billing_country' THEN um.meta_value END) AS country,
                MAX(CASE WHEN um.meta_key = 'billing_state' THEN um.meta_value END) AS state,
                MAX(CASE WHEN um.meta_key = 'billing_vat' THEN um.meta_value END) AS vat

            FROM wpjc_users u
            LEFT JOIN wpjc_usermeta um ON u.ID = um.user_id

            WHERE 
                u.user_email = %s
                OR REPLACE(REPLACE(um.meta_value, ' ', ''), '+351', '') = REPLACE(REPLACE(%s, ' ', ''), '+351', '')

            GROUP BY u.ID
            LIMIT 1
            """

            cursor.execute(query, (search, search))
            return cursor.fetchone()

    finally:
        conn.close()


# =========================
# OBTER ENCOMENDAS HPOS
# =========================

def get_orders(user_id):
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            query = """
            SELECT 
                id,
                status,
                currency,
                total_amount,
                date_created_gmt
            FROM wpjc_wc_orders
            WHERE customer_id = %s
            ORDER BY date_created_gmt DESC
            """

            cursor.execute(query, (user_id,))
            return cursor.fetchall()

    finally:
        conn.close()


# =========================
# OBTER SUBSCRIÇÕES YITH
# =========================

def is_subscription_overdue(timestamp_value):
    if not timestamp_value:
        return False

    try:
        due_date = datetime.fromtimestamp(int(timestamp_value), tz=timezone.utc)
        now = datetime.now(timezone.utc)
        return due_date < now
    except Exception:
        return False


def get_subscriptions(user_id):
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            query = """
            SELECT 
                p.ID,

                MAX(CASE WHEN pm.meta_key = 'product_id' THEN pm.meta_value END) AS product_id,
                MAX(CASE WHEN pm.meta_key = 'variation_id' THEN pm.meta_value END) AS variation_id,
                MAX(CASE WHEN pm.meta_key = 'product_name' THEN pm.meta_value END) AS product_name,
                MAX(CASE WHEN pm.meta_key = 'status' THEN pm.meta_value END) AS status,
                MAX(CASE WHEN pm.meta_key = 'subscription_total' THEN pm.meta_value END) AS total,
                MAX(CASE WHEN pm.meta_key = 'order_id' THEN pm.meta_value END) AS order_id,
                MAX(CASE WHEN pm.meta_key = 'start_date' THEN pm.meta_value END) AS start_date,
                MAX(CASE WHEN pm.meta_key = 'payment_due_date' THEN pm.meta_value END) AS next_payment,
                MAX(CASE WHEN pm.meta_key = 'payment_method_title' THEN pm.meta_value END) AS payment_method,
                MAX(CASE WHEN pm.meta_key = 'price_is_per' THEN pm.meta_value END) AS price_is_per,
                MAX(CASE WHEN pm.meta_key = 'price_time_option' THEN pm.meta_value END) AS price_time_option

            FROM wpjc_posts p
            LEFT JOIN wpjc_postmeta pm ON pm.post_id = p.ID

            WHERE 
                p.post_type = 'ywsbs_subscription'
                AND EXISTS (
                    SELECT 1
                    FROM wpjc_postmeta pm2
                    WHERE pm2.post_id = p.ID
                    AND pm2.meta_key = 'user_id'
                    AND pm2.meta_value = %s
                )

            GROUP BY p.ID
            ORDER BY p.ID DESC
            """

            cursor.execute(query, (user_id,))
            return cursor.fetchall()

    finally:
        conn.close()


# =========================
# ESTADO VISUAL SUBSCRIÇÃO
# =========================

def show_subscription_status(status):
    if status == "active":
        st.success("Ativa")
    elif status == "cancelled":
        st.error("Cancelada")
    elif status == "paused":
        st.warning("Pausada")
    elif status == "expired":
        st.error("Expirada")
    elif status == "pending":
        st.info("Pendente")
    else:
        st.write(status if status else "-")


# =========================
# APP STREAMLIT
# =========================

st.set_page_config(
    page_title="Cliente 360",
    page_icon="🔎",
    layout="wide"
)

st.title("🔎 Clientes Stellae Studio")

search = st.text_input("Pesquisa por **email** ou **telefone** do cliente.")

if st.button("Pesquisar"):

    if not search:
        st.warning("Insere um email ou telefone.")
        st.stop()

    try:
        cliente = get_customer(search)

        if not cliente:
            st.error("Cliente não encontrado.")
            st.stop()

        user_id = cliente["ID"]

        st.success("Cliente encontrado.")

        # =========================
        # DADOS DO CLIENTE
        # =========================

        st.subheader("👤 Dados do Cliente")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("###")
            st.write(f"**ID:** {cliente['ID']}")
            st.write(f"**Nome:** {cliente['first_name'] or '-'} {cliente['last_name'] or '-'}")
            st.write(f"**Email:** {cliente['user_email'] or '-'}")
            st.write(f"**Telefone:** {cliente['phone'] or '-'}")
            st.write(f"**Data de nascimento:** {cliente['birth_date'] or '-'}")

        with col2:
            st.markdown("### Informação Extra")
            st.write(f"**Nome encarregado de educação:** {cliente['encarregado'] or '-'}")
            st.write(f"**Problema de saúde:** {cliente['problema_saude'] or '-'}")

        st.markdown("---")

        st.markdown("### 🧾 Dados de Faturação")

        col3, col4 = st.columns(2)

        with col3:
            st.write(f"**Empresa:** {cliente['company'] or '-'}")
            st.write(f"**Morada linha 1:** {cliente['address1'] or '-'}")
            st.write(f"**Morada linha 2:** {cliente['address2'] or '-'}")
            st.write(f"**Cidade:** {cliente['city'] or '-'}")

        with col4:
            st.write(f"**Código postal:** {cliente['postcode'] or '-'}")
            st.write(f"**País:** {cliente['country'] or '-'}")
            st.write(f"**Distrito/Município:** {cliente['state'] or '-'}")
            st.write(f"**NIF:** {cliente['vat'] or '-'}")

        st.markdown("---")

        # =========================
        # ENCOMENDAS
        # =========================

        st.subheader("🛒 Encomendas")

        orders = get_orders(user_id)

        if orders:
            df_orders = pd.DataFrame(orders)

            df_orders = df_orders.rename(columns={
                "id": "Encomenda",
                "status": "Estado",
                "currency": "Moeda",
                "total_amount": "Total",
                "date_created_gmt": "Data"
            })

            st.dataframe(df_orders, width="stretch")
        else:
            st.info("Este cliente ainda não tem encomendas.")

        st.markdown("---")

        # =========================
        # SUBSCRIÇÕES
        # =========================

        st.subheader("🔁 Assinaturas")

        subscriptions = get_subscriptions(user_id)

        if subscriptions:
            for sub in subscriptions:
                with st.container():
                    st.markdown(f"### Assinatura #{sub['ID']}")

                    col5, col6, col7 = st.columns(3)

                    with col5:
                        st.write(f"**Produto:** {sub['product_name'] or '-'}")
                        st.write(f"**Produto ID:** {sub['product_id'] or '-'}")
                        st.write(f"**Variação ID:** {sub['variation_id'] or '-'}")

                    with col6:
                        st.write("**Estado:**")
                        show_subscription_status(sub["status"])
                        st.write(f"**Total:** {sub['total'] or '-'} €")
                        st.write(f"**Encomenda:** #{sub['order_id'] or '-'}")

                    with col7:
                        st.write(f"**Início:** {format_timestamp(sub['start_date'])}")
                        if is_subscription_overdue(sub["next_payment"]):
                            st.error(f"Próximo pagamento vencido: {format_timestamp(sub['next_payment'])}")
                        else:
                            st.success(f"Próximo pagamento: {format_timestamp(sub['next_payment'])}")
                        st.write(f"**Método pagamento:** {sub['payment_method'] or '-'}")
                        st.write(f"**Periodo:** {sub['price_is_per'] or '-'} {sub['price_time_option'] or ''}")

                    st.markdown("---")
        else:
            st.info("Este cliente ainda não tem assinaturas.")

    except Exception as e:
        st.error("Ocorreu um erro ao consultar a base de dados.")
        st.exception(e)