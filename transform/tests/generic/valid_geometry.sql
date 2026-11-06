{% test valid_geometry(model, column_name) %}
select * from {{ model }} where not ST_IsValid({{ column_name }})
{% endtest %}
