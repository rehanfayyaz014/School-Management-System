template = open('app/templates/student_overall_report_src.html', encoding='utf-8').read()
with open('app/templates/student_overall_report.html', 'w', encoding='utf-8') as f:
    f.write(template)
print('Done', len(template))
