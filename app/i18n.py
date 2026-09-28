"""Textos de la web en español e inglés. Añadir aquí cualquier texto nuevo."""

TEXTS = {
    "es": {
        "app_title": "Análisis BESS · Mercado eléctrico español",
        "home_intro": (
            "Plataforma de análisis del mercado diario español orientada a baterías "
            "(BESS): spreads, ingresos de arbitraje y su evolución."
        ),
        "home_status": "Versión en construcción. Páginas disponibles:",
        "page_daily": "Ingresos diarios de arbitraje",
        "daily_title": "Ingresos diarios de arbitraje por duración",
        "daily_caption": (
            "Batería de 1 MW, eficiencia {rte:.0%}, {cycles:g} ciclo/día. "
            "Método: optimización con previsión perfecta."
        ),
        "kpi_year": "{dur} h · €/MW·año",
        "smoothing": "Media móvil de 7 días",
        "y_axis": "€/MW·día",
        "duration": "Duración",
        "no_data": (
            "Todavía no hay datos. Ejecuta primero scripts.backfill_prices y "
            "scripts.compute_bess_daily."
        ),
        "data_table": "Ver datos en tabla",
        "period": "Periodo: {start} – {end} ({days} días)",
        "cta": "¿Analizamos tu proyecto? Contacta con {company}",
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
        "page_daily": "Daily arbitrage revenues",
        "daily_title": "Daily arbitrage revenues by duration",
        "daily_caption": (
            "1 MW battery, {rte:.0%} round-trip efficiency, {cycles:g} cycle/day. "
            "Method: optimisation with perfect foresight."
        ),
        "kpi_year": "{dur} h · €/MW·year",
        "smoothing": "7-day moving average",
        "y_axis": "€/MW·day",
        "duration": "Duration",
        "no_data": (
            "No data yet. Run scripts.backfill_prices and scripts.compute_bess_daily first."
        ),
        "data_table": "Show data table",
        "period": "Period: {start} – {end} ({days} days)",
        "cta": "Shall we analyse your project? Contact {company}",
        "cta_button": "Contact",
        "disclaimer": (
            "Day-ahead market arbitrage with perfect foresight. Indicative results, "
            "not investment advice."
        ),
        "source": "Data source: OMIE (day-ahead marginal price, Spanish zone).",
    },
}
