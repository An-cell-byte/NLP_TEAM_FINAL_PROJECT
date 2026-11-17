-- Ejecutar únicamente dentro de una base NUEVA de demostración.
CREATE TABLE usuarios(id INTEGER PRIMARY KEY,nombre VARCHAR(80));
CREATE TABLE prestamos(id INTEGER PRIMARY KEY,usuario_id INTEGER,libro VARCHAR(100),importe DECIMAL(10,2),fecha DATE,FOREIGN KEY(usuario_id) REFERENCES usuarios(id));
INSERT INTO usuarios VALUES(10,'Ana'),(20,'Luis');
INSERT INTO prestamos VALUES(1,10,'PLN aplicado',12.50,'2026-11-01'),(2,10,'Bases de datos',7.50,'2026-11-02'),(3,20,'Redes neuronales',NULL,'2026-11-02');
CREATE VIEW prestamos_detalle AS SELECT p.id,p.usuario_id,u.nombre,p.libro,p.importe,p.fecha FROM prestamos p JOIN usuarios u ON u.id=p.usuario_id;
