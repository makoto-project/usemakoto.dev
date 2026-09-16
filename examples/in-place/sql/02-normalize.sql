UPDATE customers
SET email = lower(trim(email)),
    marketing_consent = CASE lower(trim(marketing_consent))
      WHEN 'yes' THEN 1 WHEN 'true' THEN 1 WHEN '1' THEN 1
      WHEN 'no' THEN 0 WHEN 'false' THEN 0 WHEN '0' THEN 0
    END,
    region = upper(region);
