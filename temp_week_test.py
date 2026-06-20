import datetime

def get_working_days_for_week(year, week, exclude_holidays):
    d = datetime.date.fromisocalendar(year, week, 1)
    days = 0
    for i in range(5):
        dt = d + datetime.timedelta(days=i)
        if dt.strftime('%Y-%m-%d') not in exclude_holidays:
            days += 1
    return days

holidays_to_exclude = ['2026-05-01', '2026-05-05', '2026-05-25']
print(f"W21 working days: {get_working_days_for_week(2026, 21, holidays_to_exclude)}")
print(f"W22 working days: {get_working_days_for_week(2026, 22, holidays_to_exclude)}")
print(f"W19 working days: {get_working_days_for_week(2026, 19, holidays_to_exclude)}")
