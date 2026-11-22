-- ============================================================================
-- ScriptBD_DSL_final.sql - Script FINAL de la base de datos (Laboratorio A7)
-- Estructura y datos de la base después de procesar el archivo CSV con
-- ProcesaSQL.py (solo se ejecutaron las sentencias válidas).
-- Generado: 2026-11-21 19:17:53   Servidor MySQL: 8.0.46
-- ============================================================================

CREATE DATABASE IF NOT EXISTS `ubosquebd` DEFAULT CHARACTER SET utf8mb4;
USE `ubosquebd`;

-- Estructura de la tabla `usuarios`
DROP TABLE IF EXISTS `usuarios`;
CREATE TABLE `usuarios` (
  `login` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `password` varchar(15) NOT NULL,
  `estado` varchar(15) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Datos de la tabla `usuarios` (15 registros)
INSERT INTO `usuarios` (`login`, `password`, `estado`) VALUES
('carlos_h', '123456', 'suspendido'),
('juan_perez1', '123456', 'pendiente'),
('juan_perez2', '123456', 'pendiente'),
('juan_perez3', '123457', 'pendiente'),
('juan_perez4', '123458', 'pendiente'),
('guest', '123456', 'inactivo'),
('maria99', 'secret', 'suspendido'),
('guest', 'qwerty', 'activo'),
('maria99', 'SecurePass#1', 'pendiente'),
('admin', 'secret', 'inactivo'),
('carlos_m', '123456', 'activo'),
('guest', 'Abc@2026', 'inactivo'),
('guest', 'password!', 'pendiente'),
('test_user', 'password!', 'activo'),
('carlos_m', 'pass123', 'pendiente');

