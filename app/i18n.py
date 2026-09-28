"""Textos de la web en español e inglés. Añadir aquí cualquier texto nuevo."""

TEXTS = {
    "es": {
        "app_title": "Análisis BESS · Mercado eléctrico español",
        "home_intro": (
            "Plataforma de análisis del mercado diario español orientada a baterías "
            "(BESS): spreads, ingresos de arbitraje y su evolución."
        ),
        "home_status": "Versión en construcción. Páginas disponibles:",
        "page_calc": "Calculadora de arbitraje BESS",
        "calc_title": "Calculadora de arbitraje BESS",
        "calc_intro": (
            "Elige el periodo y las características de la batería. El cálculo optimiza "
            "cada día la carga y descarga en el mercado diario con previsión perfecta."
        ),
        "period_input": "Periodo",
        "power": "Potencia (MW)",
        "energy": "Capacidad (MWh)",
        "rte": "Eficiencia ida y vuelta (%)",
        "cycles": "Ciclos máximos al día",
        "soc": "Estado de carga mínimo y máximo (%)",
        "degradation": "Coste de degradación (€/MWh descargado)",
        "duration_info": "Duración: {dur:g} h",
        "period_incomplete": "Elige la fecha de inicio y la de fin del periodo.",
        "soc_invalid": "El estado de carga mínimo debe ser menor que el máximo.",
        "no_days": "No hay días con datos completos en el periodo elegido.",
        "computing": "Calculando {days} días…",
        "kpi_total": "Ingreso total del periodo",
        "kpi_year": "Ingreso anual equivalente",
        "kpi_year_mw": "{value} €/MW·año",
        "kpi_cycles": "Ciclos medios al día",
        "kpi_days": "Días analizados",
        "daily_chart": "Ingreso diario",
        "monthly_chart": "Ingreso mensual",
        "smoothing": "Media móvil de 7 días",
        "y_day": "€/día",
        "y_month": "€/mes",
        "partial_months": "En tono claro, meses que el periodo no cubre completos.",
        "no_data": (
            "Todavía no hay datos. Ejecuta primero scripts.backfill_prices."
        ),
        "data_table": "Ver datos en tabla",
        "col_date": "Fecha",
        "col_revenue": "Ingreso (€)",
        "col_cycles": "Ciclos",
        "col_buy": "Precio medio compra (€/MWh)",
        "col_sell": "Precio medio venta (€/MWh)",
        "col_spread": "Spread máx−mín (€/MWh)",
        "cta": "¿Analizamos tu proyecto? Contacta con nosotros",
        "cta_button": "Contactar",
        "disclaimer": (
            "Arbitraje en el mercado diario con previsión perfecta. Resultados "
            "orientativos, no constituyen asesoramiento de inversión."
        ),
        "source": "Fuente de los datos: OMIE (precio marginal del mercado diario, zona española).",
    },
    "en": {
        "app_title": "BESS Analytics · Spanish power market",
        "home_intro": (
            "Analytics platform for battery storage (BESS) on the Spanish day-ahead "
            "market: spreads, arbitrage revenues and their evolution."
        ),
        "home_status": "Work in progress. Available pages:",
        "page_calc": "BESS arbitrage calculator",
        "calc_title": "BESS arbitrage calculator",
        "calc_intro": (
            "Choose the period and the battery specifications. Each day, charging and "
            "discharging on the day-ahead market is optimised with perfect foresight."
        ),
        "period_input": "Period",
        "power": "Power (MW)",
        "energy": "Capacity (MWh)",
        "rte": "Round-trip efficiency (%)",
        "cycles": "Maximum cycles per day",
        "soc": "Minimum and maximum state of charge (%)",
        "degradation": "Degradation cost (€/MWh discharged)",
        "duration_info": "Duration: {dur:g} h",
        "period_incomplete": "Choose both the start and end date of the period.",
        "soc_invalid": "Minimum state of charge must be lower than the maximum.",
        "no_days": "There are no days with complete data in the selected period.",
        "computing": "Computing {days} days…",
        "kpi_total": "Total revenue for the period",
        "kpi_year": "Annualised revenue",
        "kpi_year_mw": "{value} €/MW·year",
        "kpi_cycles": "Average cycles per day",
        "kpi_days": "Days analysed",
        "daily_chart": "Daily revenue",
        "monthly_chart": "Monthly revenue",
        "smoothing": "7-day moving average",
        "y_day": "€/day",
        "y_month": "€/month",
        "partial_months": "Lighter bars: months not fully covered by the period.",
        "no_data": "No data yet. Run scripts.backfill_prices first.",
        "data_table": "Show data table",
        "col_date": "Date",
        "col_revenue": "Revenue (€)",
        "col_cycles": "Cycles",
        "col_buy": "Average buy price (€/MWh)",
        "col_sell": "Average sell price (€/MWh)",
        "col_spread": "Max−min spread (€/MWh)",
        "cta": "Shall we analyse your project? Get in touch",
        "cta_button": "Contact",
        "disclaimer": (
            "Day-ahead market arbitrage with perfect foresight. Indicative results, "
            "not investment advice."
        ),
        "source": "Data source: OMIE (day-ahead marginal price, Spanish zone).",
    },
}
