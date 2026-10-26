# utils/memoria.py
# Instrumentación ligera de memoria para los logs de Render (sin dependencias).
#
# Cada línea tiene el formato fácil de buscar:
#   [MEM] etapa=<nombre> proceso_rss_mb=<n> proceso_pico_mb=<n> contenedor_mb=<n> contenedor_limite_mb=<n>
#
# - proceso_*   : memoria del proceso de Python (VmRSS / VmHWM de /proc/self/status).
# - contenedor_*: memoria del cgroup de la instancia (la que Render compara con
#                 el límite de 512 MB). Incluye caché de archivos del kernel, por
#                 lo que puede ser mayor que el RSS del proceso.
# Fuera de Linux (o si el dato no está disponible) el valor se informa como "n/d".
# Nunca imprime datos de negocio y nunca interrumpe la aplicación.

import time

_ultimaVez: dict[str, float] = {}


def _leerTexto(ruta: str) -> str | None:
    try:
        with open(ruta, encoding="ascii", errors="ignore") as f:
            return f.read().strip()
    except OSError:
        return None


def _mb(bytesValor: int) -> str:
    return f"{bytesValor / (1024 * 1024):.1f}"


def _memoriaProceso() -> tuple[str, str]:
    """(rss_mb, pico_mb) del proceso, o ("n/d", "n/d")."""
    texto = _leerTexto("/proc/self/status")
    if not texto:
        return "n/d", "n/d"
    valores = {}
    for linea in texto.splitlines():
        if linea.startswith(("VmRSS:", "VmHWM:")):
            partes = linea.split()
            if len(partes) >= 2 and partes[1].isdigit():
                valores[partes[0]] = int(partes[1]) * 1024  # kB -> bytes
    rss = _mb(valores["VmRSS:"]) if "VmRSS:" in valores else "n/d"
    pico = _mb(valores["VmHWM:"]) if "VmHWM:" in valores else "n/d"
    return rss, pico


def _memoriaContenedor() -> tuple[str, str]:
    """(uso_mb, limite_mb) del cgroup (v2 o v1), o ("n/d", "n/d")."""
    uso = _leerTexto("/sys/fs/cgroup/memory.current") or _leerTexto(
        "/sys/fs/cgroup/memory/memory.usage_in_bytes"
    )
    limite = _leerTexto("/sys/fs/cgroup/memory.max") or _leerTexto(
        "/sys/fs/cgroup/memory/memory.limit_in_bytes"
    )
    usoMb = _mb(int(uso)) if uso and uso.isdigit() else "n/d"
    # "max" (v2) o un valor enorme (v1) significan "sin límite configurado".
    if limite and limite.isdigit() and int(limite) < (1 << 50):
        limiteMb = _mb(int(limite))
    else:
        limiteMb = "n/d"
    return usoMb, limiteMb


def registrarMemoria(etapa: str, minIntervaloSeg: float = 0.0, unaVez: bool = False) -> None:
    """
    Escribe una línea [MEM] en stdout (logs de Render).

    Args:
        etapa:           Nombre de la etapa (identificador sin datos personales).
        minIntervaloSeg: Si > 0, omite el registro si esta misma etapa ya se
                         registró hace menos de ese número de segundos.
        unaVez:          Si True, registra la etapa solo una vez por proceso
                         (los módulos de utils/ persisten entre reruns).
    """
    try:
        ahora = time.monotonic()
        previo = _ultimaVez.get(etapa)
        if previo is not None and (unaVez or ahora - previo < minIntervaloSeg):
            return
        _ultimaVez[etapa] = ahora

        rss, pico = _memoriaProceso()
        uso, limite = _memoriaContenedor()
        print(
            f"[MEM] etapa={etapa} proceso_rss_mb={rss} proceso_pico_mb={pico} "
            f"contenedor_mb={uso} contenedor_limite_mb={limite}",
            flush=True,
        )
    except Exception:
        # La instrumentación jamás debe afectar a la aplicación.
        pass
