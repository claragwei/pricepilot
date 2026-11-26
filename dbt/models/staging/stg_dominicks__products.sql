-- Product descriptions for the loaded categories.
{% for c in var('movement_categories') %}
select
    '{{ c }}' as category,
    upc,
    com_code,
    descrip as description,
    size,
    "case" as case_pack,
    nitem
from {{ source('raw', 'upc' ~ c) }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
