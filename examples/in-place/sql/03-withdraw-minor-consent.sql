UPDATE customers
SET marketing_consent = 0
WHERE age < 18 AND marketing_consent = 1;
