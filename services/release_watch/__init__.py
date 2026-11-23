"""Databricks Release Watch: monitoramento recorrente das release notes oficiais do
Azure Databricks, integrado a curadoria editorial (nada e publicado sem aprovacao).

Modulos: periods (calendario UTC), parser (extracao + sanitizacao), classify (areas e
relevancia), store (Delta/SQLite), runner (execucao idempotente), publish (revisao e
sobreposicao ao catalogo). O agendamento roda em Lakeflow Jobs (jobs/release_watch_job.py).
"""
