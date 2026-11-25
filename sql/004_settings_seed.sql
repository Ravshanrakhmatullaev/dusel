-- Boshlang'ich sozlamalar (mavjud bo'lsa o'zgartirmaydi)
insert into checkin.settings (key, value) values
  ('environment', '"STAGING"'), ('event_label', '"DUSEL GROUP — Yulduzli Kecha · 23.12.2026 · Humo Arena"'),
  ('admission_open', 'false'), ('block_held_stock', 'true'), ('capacity', '11222'), ('rate_limit_per_10s', '40')
on conflict (key) do nothing;
insert into checkin.gates (gate_id, name) values ('G1', '1-kirish'), ('G2', '2-kirish'), ('G3', '3-kirish'), ('G4', '4-kirish'), ('VIP', 'VIP kirish')
on conflict (gate_id) do nothing;
