-- Consultas de los gránulos de conocimiento por hipótesis (SQLite 3).
-- Un gránulo es la unidad mínima de conocimiento que el motor recupera por
-- separado: la hipótesis, la regla que la concluye, las condiciones (síntomas)
-- de esa regla, su camino en el árbol y su solución.
-- Para consultar otra falla, reemplace 'F17' por el código de la hipótesis.

-- G1. Ficha de la hipótesis: datos, categoría, fuente (experto) y solución.
SELECT h.codigo, h.nombre, c.nombre AS categoria, h.severidad,
       h.factor_certeza, e.nombre AS fuente_experto, h.solucion
FROM hipotesis h
JOIN categoria c ON c.id = h.categoria_id
JOIN experto   e ON e.id = h.experto_id
WHERE h.codigo = 'F17';

-- G2. Regla que concluye la hipótesis.
SELECT r.codigo AS regla, h.codigo AS hipotesis, r.factor_certeza
FROM regla r
JOIN hipotesis h ON h.id = r.hipotesis_id
WHERE h.codigo = 'F17';

-- G3. Premisas de la regla: síntomas y valor esperado, en el orden del camino.
SELECT r.codigo AS regla, rc.orden, s.codigo AS sintoma, s.pregunta,
       CASE rc.valor WHEN 'si' THEN 'SÍ' ELSE 'NO' END AS valor
FROM regla_condicion rc
JOIN regla r     ON r.id = rc.regla_id
JOIN hipotesis h ON h.id = r.hipotesis_id
JOIN sintoma s   ON s.id = rc.sintoma_id
WHERE h.codigo = 'F17'
ORDER BY rc.orden;

-- G4. Camino del árbol hasta la hoja de la hipótesis (de la raíz a la hoja).
WITH RECURSIVE camino(id, codigo, padre_id, rama, sintoma_id, nivel) AS (
    SELECT n.id, n.codigo, n.padre_id, n.rama, n.sintoma_id, 0
    FROM nodo_arbol n
    JOIN hipotesis h ON h.id = n.hipotesis_id
    WHERE h.codigo = 'F17'
    UNION ALL
    SELECT p.id, p.codigo, p.padre_id, p.rama, p.sintoma_id, camino.nivel + 1
    FROM nodo_arbol p
    JOIN camino ON p.id = camino.padre_id
)
SELECT camino.nivel AS pasos_a_la_hoja, camino.codigo AS nodo,
       camino.rama AS rama_desde_padre, s.codigo AS sintoma
FROM camino
LEFT JOIN sintoma s ON s.id = camino.sintoma_id
ORDER BY camino.nivel DESC;

-- G5. Resumen de todos los gránulos: hipótesis, regla y número de premisas.
SELECT h.codigo AS hipotesis, h.nombre, r.codigo AS regla,
       COUNT(rc.orden) AS premisas
FROM hipotesis h
JOIN regla r ON r.hipotesis_id = h.id
JOIN regla_condicion rc ON rc.regla_id = r.id
GROUP BY h.id
ORDER BY h.codigo;

-- G6. Hipótesis que comparten un síntoma (sirve para validar con el experto).
SELECT sintoma, valor,
       COUNT(DISTINCT hipotesis) AS hipotesis_que_lo_usan,
       GROUP_CONCAT(hipotesis, ', ') AS hipotesis
FROM (SELECT s.codigo AS sintoma, rc.valor, h.codigo AS hipotesis
      FROM regla_condicion rc
      JOIN regla r     ON r.id = rc.regla_id
      JOIN hipotesis h ON h.id = r.hipotesis_id
      JOIN sintoma s   ON s.id = rc.sintoma_id
      WHERE s.codigo = 'S01'
      ORDER BY h.codigo)
GROUP BY sintoma, valor
ORDER BY valor DESC;

-- G7. Regla completa en una sola fila, con la forma SI ... ENTONCES ...
SELECT r.codigo AS regla,
       'SI ' || GROUP_CONCAT(p.condicion, ' Y ') || ' ENTONCES ' || h.codigo
         AS regla_textual
FROM regla r
JOIN hipotesis h ON h.id = r.hipotesis_id
JOIN (SELECT rc.regla_id,
             s.codigo || ' = ' || CASE rc.valor WHEN 'si' THEN 'SÍ' ELSE 'NO' END
               AS condicion
      FROM regla_condicion rc
      JOIN sintoma s ON s.id = rc.sintoma_id
      ORDER BY rc.regla_id, rc.orden) p ON p.regla_id = r.id
WHERE h.codigo = 'F17'
GROUP BY r.id;
