SET datestyle = 'ISO, DMY';
CREATE TABLE IF NOT EXISTS "Account" (
    "ID" SERIAL PRIMARY KEY,
    "Username" VARCHAR(50),
    "Joined" DATE,
    "Role" VARCHAR(20),
    "DateOfBirth" DATE,
    "MagneticCode" VARCHAR(20)
);
COPY "Account"("ID", "Username", "Joined", "Role", "DateOfBirth", "MagneticCode")
FROM '/postgresql/data/account.csv'
DELIMITER ','
CSV HEADER;