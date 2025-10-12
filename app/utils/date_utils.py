"""
Utilidades de fecha para la aplicación Gen-AvatART.

Este módulo proporciona funciones auxiliares para el manejo de fechas
que son compatibles con todos los motores de base de datos. Evita el uso
de funciones específicas de BD como db.extract() que no funcionan universalmente.

Funcionalidades principales:
    - Cálculo de rangos mensuales
    - Rangos de fechas compatibles con todos los motores SQL
    - Utilidades para estadísticas temporales
    - Funciones reutilizables para consultas de fecha
"""

from datetime import datetime, date
from typing import Tuple

def get_month_range(year: int, month: int) -> Tuple[datetime, datetime]:
    """
    Obtiene el rango de fechas de un mes específico.
    
    Esta función es compatible con todos los motores de base de datos
    ya que utiliza rangos de fechas estándar en lugar de funciones
    específicas de BD como EXTRACT().
    
    Args:
        year (int): Año del mes deseado
        month (int): Mes deseado (1-12)
    
    Returns:
        tuple: (start_date, end_date) donde:
               - start_date: Primer día del mes a las 00:00:00
               - end_date: Primer día del mes siguiente a las 00:00:00
    
    Example:
        >>> start, end = get_month_range(2025, 10)
        >>> # start = 2025-10-01 00:00:00
        >>> # end = 2025-11-01 00:00:00
    
    Note:
        - El end_date es exclusivo (usar < en lugar de <=)
        - Maneja correctamente el cambio de año (diciembre -> enero)
        - Compatible con SQLite, PostgreSQL, MySQL, SQL Server
    """
    start_date = datetime(year, month, 1)
    
    # Calcular el primer día del siguiente mes
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    return start_date, end_date

def get_current_month_range() -> Tuple[datetime, datetime]:
    """
    Obtiene el rango de fechas del mes actual.
    
    Returns:
        tuple: (start_date, end_date) del mes actual
    
    Note:
        - Wrapper convenience para get_month_range() del mes actual
        - Útil para estadísticas del mes en curso
    """
    current_date = datetime.now()
    return get_month_range(current_date.year, current_date.month)

def get_last_month_range() -> Tuple[datetime, datetime]:
    """
    Obtiene el rango de fechas del mes anterior.
    
    Returns:
        tuple: (start_date, end_date) del mes anterior
    
    Note:
        - Maneja correctamente el cambio de año (enero -> diciembre anterior)
        - Útil para comparaciones mes a mes
    """
    current_date = datetime.now()
    
    if current_date.month == 1:
        # Si estamos en enero, el mes anterior es diciembre del año anterior
        return get_month_range(current_date.year - 1, 12)
    else:
        # Mes anterior del mismo año
        return get_month_range(current_date.year, current_date.month - 1)

def get_year_range(year: int) -> Tuple[datetime, datetime]:
    """
    Obtiene el rango de fechas de un año específico.
    
    Args:
        year (int): Año deseado
    
    Returns:
        tuple: (start_date, end_date) del año
    
    Note:
        - start_date: 1 de enero a las 00:00:00
        - end_date: 1 de enero del año siguiente a las 00:00:00
    """
    start_date = datetime(year, 1, 1)
    end_date = datetime(year + 1, 1, 1)
    return start_date, end_date

def get_current_year_range() -> Tuple[datetime, datetime]:
    """
    Obtiene el rango de fechas del año actual.
    
    Returns:
        tuple: (start_date, end_date) del año actual
    """
    current_year = datetime.now().year
    return get_year_range(current_year)

def get_date_range_filter_params(start_date: datetime, end_date: datetime) -> dict:
    """
    Genera parámetros de filtro estándar para consultas SQLAlchemy.
    
    Args:
        start_date (datetime): Fecha de inicio (inclusiva)
        end_date (datetime): Fecha de fin (exclusiva)
    
    Returns:
        dict: Diccionario con parámetros para filter()
    
    Example:
        >>> start, end = get_current_month_range()
        >>> params = get_date_range_filter_params(start, end)
        >>> reels = user.reels.filter(**params).all()
    
    Note:
        - Usar con Model.created_at u otro campo datetime
        - El patrón >= start_date AND < end_date es universal
    """
    return {
        'created_at__gte': start_date,  # Mayor o igual
        'created_at__lt': end_date      # Menor que (exclusivo)
    }

def filter_by_date_range(query, date_field, start_date: datetime, end_date: datetime):
    """
    Aplica filtro de rango de fechas a una consulta SQLAlchemy.
    
    Args:
        query: Consulta SQLAlchemy base
        date_field: Campo de fecha del modelo (ej: Model.created_at)
        start_date (datetime): Fecha de inicio (inclusiva)
        end_date (datetime): Fecha de fin (exclusiva)
    
    Returns:
        Query: Consulta filtrada por rango de fechas
    
    Example:
        >>> start, end = get_current_month_range()
        >>> reels = filter_by_date_range(user.reels, Reel.created_at, start, end)
        >>> monthly_reels = reels.all()
    
    Note:
        - Método universal compatible con todos los motores de BD
        - Reemplaza el uso de db.extract() y funciones específicas
    """
    return query.filter(
        date_field >= start_date,
        date_field < end_date
    )

def get_monthly_stats_helper(user_relation, model_class, cost_field=None):
    """
    Helper function para calcular estadísticas mensuales de cualquier modelo.
    
    Args:
        user_relation: Relación del usuario (ej: user.reels, user.commissions)
        model_class: Clase del modelo (ej: Reel, Commission)
        cost_field (str, optional): Nombre del campo de costo/amount
    
    Returns:
        dict: Estadísticas mensuales con totales y comparaciones
    
    Example:
        >>> stats = get_monthly_stats_helper(user.reels, Reel, 'cost')
        >>> # Retorna: {'this_month_count': 5, 'this_month_total': 45.50, ...}
    
    Note:
        - Reutilizable para diferentes modelos y campos
        - Calcula automáticamente mes actual vs mes anterior
        - Compatible con todos los motores de BD
    """
    current_start, current_end = get_current_month_range()
    last_start, last_end = get_last_month_range()
    
    # Filtrar registros del mes actual
    current_month_items = filter_by_date_range(
        user_relation, 
        getattr(model_class, 'created_at'), 
        current_start, 
        current_end
    ).all()
    
    # Filtrar registros del mes anterior
    last_month_items = filter_by_date_range(
        user_relation,
        getattr(model_class, 'created_at'),
        last_start,
        last_end
    ).all()
    
    stats = {
        'this_month_count': len(current_month_items),
        'last_month_count': len(last_month_items),
    }
    
    # Agregar estadísticas de costos/amounts si se especifica el campo
    if cost_field:
        stats.update({
            'this_month_total': sum([getattr(item, cost_field, 0) or 0 for item in current_month_items]),
            'last_month_total': sum([getattr(item, cost_field, 0) or 0 for item in last_month_items])
        })
    
    return stats