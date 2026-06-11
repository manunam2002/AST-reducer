CREATE TABLE tbl_wqiwo (rcol_eitnk REAL DEFAULT 1, tcol_yqthy TEXT, rcol_bjzii REAL, tcol_wskpp);
INSERT INTO tbl_wqiwo (rcol_eitnk, tcol_wskpp, tcol_yqthy) VALUES (1, 11960.180152676927, 1), (1, 1, 1);
ALTER TABLE tbl_wqiwo ADD COLUMN icol_ovpnc INTEGER;
WITH with_vysww AS (SELECT * FROM tbl_wqiwo ORDER BY tbl_wqiwo.tcol_wskpp), with_ekqzi AS (SELECT * FROM with_vysww), with_kepqw AS (SELECT * FROM with_vysww GROUP BY with_vysww.icol_ovpnc ORDER BY with_vysww.rcol_bjzii) SELECT * FROM with_kepqw