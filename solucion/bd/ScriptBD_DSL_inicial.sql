-- ============================================================================
-- ScriptBD_DSL_inicial.sql - Script INICIAL de la base de datos (Laboratorio A7)
-- Crea la base de datos ubosquebd y la tabla usuarios con sus datos de partida.
-- Basado en el script entregado (ScriptBD_DSL.sql); se agregan CREATE DATABASE,
-- USE y DROP TABLE IF EXISTS para poder reiniciar la base antes de cada prueba.
-- Uso:  python bd_util.py reiniciar     (o importarlo en phpMyAdmin / Workbench)
-- ============================================================================

CREATE DATABASE IF NOT EXISTS `ubosquebd` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `ubosquebd`;
DROP TABLE IF EXISTS `usuarios`;

-- phpMyAdmin SQL Dump
-- version 4.9.1
-- https://www.phpmyadmin.net/
--
-- Servidor: localhost
-- Tiempo de generación: 17-11-2026 a las 03:30:20
-- Versión del servidor: 8.0.17
-- Versión de PHP: 7.3.10

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET AUTOCOMMIT = 0;
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de datos: `ubosquebd`
--

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `usuarios`
--

CREATE TABLE `usuarios` (
  `login` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `password` varchar(15) NOT NULL,
  `estado` varchar(15) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Volcado de datos para la tabla `usuarios`
--

INSERT INTO `usuarios` (`login`, `password`, `estado`) VALUES
('carlos_m', 'secret', 'pendiente'),
('carlos_h', '123456', 'suspendido'),
('ana_g', 'pass123', 'inactivo'),
('user1', 'pass123', 'inactivo'),
('maria99', 'pass123', 'inactivo'),
('juan_perez', '12345', ''),
('juan_perez', '123456', 'pendiente'),
('juan_perez', '123456', 'pendiente'),
('juan_perez', '123456', 'pendiente'),
('juan_perez', '123457', 'pendiente'),
('juan_perez', '123458', 'pendiente'),
('juan_perez', '123459', 'pendiente'),
('juan_perez1', '123456', 'pendiente'),
('juan_perez2', '123456', 'pendiente'),
('juan_perez3', '123457', 'pendiente'),
('juan_perez4', '123458', 'pendiente');
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
