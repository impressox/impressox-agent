import unicodedata
from datetime import datetime, timedelta

def format_date(date_str):
    """Chuyển đổi ngày tháng từ string sang dạng datetime"""
    day_of_week, day_month_year = date_str.split(", ")
    day, month, year = day_month_year.replace("ngày ", "").split("/")
    return datetime(int(year), int(month), int(day))

def get_month_dates(current_date: datetime):
    """ Lấy from_date, to_date của tháng """

    first_day_of_month  = current_date.replace(day=1)
    
    if first_day_of_month.month == 12:
        last_day_of_month = first_day_of_month.replace(year=first_day_of_month.year + 1, month=1) - timedelta(days=1)
    else:
        last_day_of_month = first_day_of_month.replace(month=first_day_of_month.month + 1) - timedelta(days=1)

    
    return first_day_of_month.strftime("%Y%m%d"), last_day_of_month.strftime("%Y%m%d")

def get_year_dates(current_date: datetime):
    """ Lấy from_date, to_date của năm """

    first_day_of_year  = current_date.replace(month=1, day=1)

    if current_date.year == datetime.now().year:
        last_day_of_year = current_date 
    else:
        last_day_of_year = current_date.replace(month=12, day=31)
    
    return first_day_of_year.strftime("%Y%m%d"), last_day_of_year.strftime("%Y%m%d")