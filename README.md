# ¿Cuánto portafolio necesitas para retirar $1.000 al mes?

Backtest histórico de una asignación long-only (SPYG, SMH, BRK.B, IEMG, VTI) con **retiro mensual indexado**.

El año 1 retira `US$1.000/mes` (`US$12.000` en total). Desde el año 2 el retiro mensual sube **3% anual**:

| Año | Retiro mensual | Retiro anual |
|-----|----------------|--------------|
| 1   | $1.000         | $12.000      |
| 2   | $1.030         | $12.360      |
| 3   | $1.060,90      | $12.730,80   |
| …   | `1000 × 1.03^(año-1)` | |

Compara tres patrimonios iniciales: **$150k**, **$300k** y **$500k**.

No es una recomendación de inversión. Es un ejercicio educativo de **riesgo de secuencia** y sostenibilidad del retiro.

---

## Asignación

| ETF   | Peso |
|-------|------|
| SPYG  | 33%  |
| SMH   | 21%  |
| BRK.B | 21%  |
| IEMG  | 16%  |
| VTI   | 9%   |

- Rebalance al peso objetivo cada mes, el mismo día del retiro.
- Precios *total return* (`auto_adjust=True` en Yahoo Finance).
- IEMG no existía antes de octubre 2012: se encadena con retornos de EEM (correlación diaria ~0.997).
- Sin impuestos, comisiones ni buffer de efectivo.
- El retiro es nominal indexado al 3%; no ajusta la inflación real de cada país.

---

## Correr en Google Colab

1. Abre `Retiro_portafolio_Colab.ipynb`.
2. Si el repo ya está en GitHub:

```text
https://colab.research.google.com/github/Andalejo1109/Retiro-portafolio/blob/main/Retiro_portafolio_Colab.ipynb
```

3. `Entorno de ejecución → Ejecutar todas`.
4. El notebook instala dependencias, descarga precios, simula y muestra PNG + GIF.

Parámetros en la celda de configuración:

```python
START = "2006-09-01"   # prueba también "2010-01-01"
END   = "2026-08-28"
BASE  = 1000.0         # retiro mensual del año 1
COLA  = 0.03           # +3% anual desde el año 2
MAKE_GIF = True
```

---

## Correr en local

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python simular_retiro.py --start 2006-09-01 --cola 0.03 --gif
```

Otras banderas:

```bash
python simular_retiro.py --help

# Sin GIF (más rápido)
python simular_retiro.py --start 2010-01-01 --cola 0.03

# Retiro fijo, sin indexación
python simular_retiro.py --start 2006-09-01 --cola 0.00
```

Los archivos quedan en `output/`.

---

## Cómo leer el resultado

- **Línea verde / naranja / rosa:** valor del portafolio que partió en $500k / $300k / $150k.
- **Línea punteada:** dinero retirado acumulado (calendario, aunque un nivel se haya agotado).
- **✕✕ Game over:** el patrimonio no alcanzó a cubrir el retiro de ese mes.
- Un mercado 2006–2026 incluye la crisis de 2008. Eso no garantiza el próximo drawdown.

Rentabilidades pasadas no predicen rentabilidades futuras. Un retiro inicial del 8% (`$12k / $150k`) es agresivo aunque en *esta* historia haya sobrevivido.

---

## Licencia

Código libre para uso personal y educativo. Los ETF citados son marcas de sus respectivos emisores.

## Autor

Andrés Alejandro Rodríguez Lozano — economista y científico de datos.

- Web: [andalejo1109.github.io](https://andalejo1109.github.io/)
- Perfil en eToro: [@Andalejo1109](https://etoro.tw/4lkmjxn)
