CREATE TABLE IF NOT EXISTS `D_CAPCODE` (
    `PK_CAPCODE` INT(11) NOT NULL AUTO_INCREMENT,
    `CAPCODE` VARCHAR(255) NOT NULL,
    `FK_REGION` INT(11) NOT NULL DEFAULT 0,
    `DESCRIPTION` VARCHAR(255) NOT NULL DEFAULT '',
    `TYPE` enum('ambulance','brandweer','dares','gemeente','knrm','onbekend','politie','reddingsbrigade') NOT NULL DEFAULT 'onbekend',
    `CITY` VARCHAR(255) NOT NULL DEFAULT '',
    PRIMARY KEY (`PK_CAPCODE`),
    UNIQUE INDEX `UNIQUE_CAPCODE` (`CAPCODE`)
);

CREATE TABLE IF NOT EXISTS `D_REGION` (
    `PK_REGION` INT(10) unsigned NOT NULL AUTO_INCREMENT,
    `NAME` VARCHAR(255) DEFAULT NULL,
    PRIMARY KEY (`PK_REGION`)
);

CREATE TABLE IF NOT EXISTS `D_CITY` (
    `PK_CITY` INT(10) unsigned NOT NULL AUTO_INCREMENT,
    `NAME` VARCHAR(255) DEFAULT NULL,
    `ACRONYM` VARCHAR(255) DEFAULT NULL,
    PRIMARY KEY (`PK_CITY`),
    UNIQUE INDEX `SEARCH_ACRONYM` (`ACRONYM`),
    INDEX `SEARCH_NAME` (`NAME`)
);

CREATE TABLE IF NOT EXISTS `F_MESSAGE` (
    `PK_MESSAGE` INT(10) unsigned NOT NULL AUTO_INCREMENT,
    `RAW_MESSAGE` TEXT DEFAULT '' NOT NULL,
    `FK_REGION` INT(10) DEFAULT 0 NOT NULL,
    `FK_CITY` INT(10) DEFAULT 0 NOT NULL,
    `MESSAGE` TEXT DEFAULT '' NOT NULL,
    `DATE` DATETIME NOT NULL,
    `STREET` VARCHAR(255) DEFAULT '' NOT NULL,
    `POSTALCODE` VARCHAR(12) DEFAULT '' NOT NULL,
    `TYPE` enum('ambulance','brandweer','dares','gemeente','knrm','onbekend','politie','reddingsbrigade') NOT NULL DEFAULT 'onbekend',
    PRIMARY KEY (`PK_MESSAGE`),
    UNIQUE INDEX `SEARCH_BY_MESSAGE_DATE` (`MESSAGE`, `DATE`)
);

CREATE TABLE IF NOT EXISTS `X_MESSAGE_CAPCODE` (
    `PK_MESSAGE_CAPCODE` INT(10) unsigned NOT NULL AUTO_INCREMENT,
    `FK_MESSAGE` INT(10) NOT NULL,
    `FK_CAPCODE` INT(10) NOT NULL,
    PRIMARY KEY (`PK_MESSAGE_CAPCODE`),
    INDEX `SEARCH_BY_MESSAGE` (`FK_MESSAGE`),
    INDEX `SEARCH_BY_CAPCODE` (`FK_CAPCODE`),
    UNIQUE INDEX `SEARCH_BY_MESSAGE_CAPCODE` (`FK_MESSAGE`, `FK_CAPCODE`)
);