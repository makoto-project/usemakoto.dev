SELECT json_group_array(json_object(
  'age', age,
  'customer_id', customer_id,
  'email', email,
  'marketing_consent', marketing_consent,
  'region', region
))
FROM (SELECT * FROM customers ORDER BY customer_id);
