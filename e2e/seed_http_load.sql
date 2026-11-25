-- HTTP yuklama testi uchun sinov xodimlari (faqat lokal/CI sinov bazasi)
insert into auth.users (email, encrypted_password) select 'load-g'||i||'@dusel.test', extensions.crypt('Load-Test-2026', extensions.gen_salt('bf',4)) from generate_series(1,8) i;
insert into checkin.staff (user_id, username, display_name, role) select id, email, email, 'GATE' from auth.users where email like 'load-g%';
insert into checkin.gates (gate_id, name) select 'L'||i, 'Yuklama '||i from generate_series(1,8) i on conflict do nothing;
update checkin.settings set value='100000' where key='rate_limit_per_10s';
