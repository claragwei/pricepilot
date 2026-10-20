-- One row per UPC in the category.
create or replace table dim_product as
select
    upc as item_id,
    trim(descrip) as description,
    trim(size) as size,
    "CASE" as case_pack,
    com_code as commodity_code,
    nitem as item_number,
    cast($category as varchar) as category
from raw_upc
order by upc
