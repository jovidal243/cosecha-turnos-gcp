-- Vista para Power BI / Looker Studio: horas y observaciones por frente y día
CREATE OR REPLACE VIEW `${PROJECT_ID}.${BQ_DATASET}.v_horas_por_frente` AS
SELECT
  fecha,
  frente_id,
  COUNT(*)                                        AS jornadas,
  ROUND(SUM(horas_trabajadas), 2)                 AS horas_trabajadas,
  ROUND(SUM(horas_extra), 2)                      AS horas_extra,
  COUNTIF(estado IN ('observado', 'rechazado'))   AS observadas,
  COUNTIF(es_anomalia)                            AS anomalias_modelo
FROM `${PROJECT_ID}.${BQ_DATASET}.jornadas_validadas`
GROUP BY fecha, frente_id;
