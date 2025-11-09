import json
from django.shortcuts import render
from django.utils.safestring import mark_safe
from datetime import datetime, date, timedelta
from django.http import JsonResponse

# Create your views here.
def dashboard_callback(request, context):

    def total_by_day_line_chart(queryset, start_date, end_date):
        current = start_date
        labels = []
        data_sets = []
        raw_data_dict = {item['day']: item['total'] for item in queryset }
        while current <= end_date:
            total = raw_data_dict.get(current, 0)
            data_sets.append([1, total])
            labels.append(str(current))
            current += timedelta(days=1)
        return {
            "labels": labels,
            "datasets": [{ "data": data_sets, "borderColor": "var(--color-primary-600)", "backgroundColor": "var(--color-primary-600)"}],
            "total": sum(data_sets[i][1] for i in range(len(data_sets)))
        }

    def create_link(url, label):
        return mark_safe(f"<a href='{ url }' class='hover:text-primary-600 dark:hover:text-primary-500'>{label}</a>")

    def create_progress_bar(value):
        return mark_safe('<div class="bg-base-100 flex flex-row overflow-hidden rounded-default dark:bg-base-800">' \
                f'<div class="h-1.5 bg-primary-600 rounded-default z-10 last:rounded-r-default dark:bg-primary-500 " title="{value}" style="width: {value}"></div></div>')


    # Get the date period filters
    start_date = request.session.get('dashboard_start_date', None)
    end_date = request.session.get('dashboard_end_date', None)
    d1 = datetime.fromisoformat(start_date).date() if start_date else date.today() - timedelta(days=30)
    d2 = datetime.fromisoformat(end_date).date() if end_date else date.today()
    if d1 > d2:
        d1, d2 = d2, d1

    if not start_date:
        request.session['dashboard_start_date'] = str(d1)
    if not end_date:
        request.session['dashboard_end_date'] = str(d2)
    start_date = d1
    end_date = d2

    return context


def dashboard_set_date_range(request):
    if request.method == "POST":
        data = json.loads(request.body)
        start_date = data.get('start_date', None)
        end_date = data.get('end_date', None)

        if start_date and end_date:
            request.session['dashboard_start_date'] = start_date
            request.session['dashboard_end_date'] = end_date
        else:
            return JsonResponse({"error": "Both start_date and end_date are required."}, status=400)

        return JsonResponse({"message": "Filter applied."})

    return JsonResponse({"error": "Invalid request method."}, status=400)