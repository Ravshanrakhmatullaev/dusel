-- E2E sinov ma'lumotlari (faqat lokal sinov bazasi)
insert into auth.users (email, encrypted_password) values
 ('admin@dusel.test', extensions.crypt('Admin-Test-2026', extensions.gen_salt('bf'))),
 ('sup@dusel.test', extensions.crypt('Sup-Test-2026', extensions.gen_salt('bf'))),
 ('gate1@dusel.test', extensions.crypt('Gate-Test-2026', extensions.gen_salt('bf'))),
 ('gate2@dusel.test', extensions.crypt('Gate-Test-2026', extensions.gen_salt('bf'))),
 ('inv@dusel.test', extensions.crypt('Inv-Test-2026', extensions.gen_salt('bf'))),
 ('nobody@dusel.test', extensions.crypt('Nobody-Test-2026', extensions.gen_salt('bf')));
insert into checkin.staff (user_id, username, display_name, role)
select id, email, d, r from auth.users join (values ('admin@dusel.test','Admin','ADMIN'),('sup@dusel.test','Nazoratchi','SUPERVISOR'),
  ('gate1@dusel.test','Darvoza-1','GATE'),('gate2@dusel.test','Darvoza-2','GATE'),('inv@dusel.test','Inventar-1','INVENTORY')) v(e,d,r) on v.e = email;
select set_config('checkin.admission_change', 'approved', false);
update checkin.settings set value = 'true' where key = 'admission_open';
select set_config('checkin.admission_change', '', false);
