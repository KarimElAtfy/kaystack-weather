import { expect, test } from 'vitest';
import {
  dec,
  humidity,
  int,
  km,
  mm,
  mmh,
  models,
  point,
  pct,
  temp,
  visibility,
  weather,
  wind
} from './format.ts';

test('prints whole numbers without a negative zero', () => {
  expect(int(-0.4)).toBe('0');
  expect(int(-2.6)).toBe('-3');
  expect(int(12.5)).toBe('13');
  expect(int(null)).toBe('n.d.');
});

test('uses a decimal comma', () => {
  expect(dec(12.25)).toBe('12,3');
  expect(mmh(1.4)).toBe('1,4 mm/h');
  expect(km(3.4)).toBe('3,4 km');
  expect(km(4)).toBe('4 km');
  expect(temp(13.4)).toBe('13 °C');
  expect(pct(88)).toBe('88%');
});

test('shows a trace of rain as under a tenth', () => {
  expect(mm(0.05)).toBe('<0,1 mm');
  expect(mm(0)).toBe('0,0 mm');
  expect(mm(3)).toBe('3,0 mm');
});

test('reads METAR visibility', () => {
  expect(visibility(9999)).toBe('oltre 10 km');
  expect(visibility(6000)).toBe('6 km');
  expect(visibility(2500)).toBe('2,5 km');
  expect(visibility(800)).toBe('800 m');
  expect(visibility(null)).toBe('n.d.');
});

test('names the wind by where it comes from', () => {
  expect(point(225)).toBe('SO');
  expect(point(359)).toBe('N');
  expect(point(-45)).toBe('NO');
  expect(wind(15.2, 225)).toBe('15 km/h da sud-ovest');
  expect(wind(15, null)).toBe('15 km/h variabile');
  expect(wind(1.5, 90)).toBe('calma');
});

test('counts models in words', () => {
  expect(models(0, 10)).toBe('nessun modello su 10');
  expect(models(1, 9)).toBe('1 modello su 9');
  expect(models(7, 10)).toBe('7 modelli su 10');
});

test('computes humidity from the dew point', () => {
  expect(humidity(13, 11)).toBe(88);
  expect(humidity(13, null)).toBeNull();
});

test('puts METAR weather groups into Italian', () => {
  expect(weather('-RA BR')).toBe('Pioggia debole, foschia');
  expect(weather('-SHRA')).toBe('Rovesci di pioggia deboli');
  expect(weather('+TSRA')).toBe('Temporale con pioggia forte');
  expect(weather('VCSH')).toBe('Rovesci nelle vicinanze');
  expect(weather('VCTS')).toBe('Temporale nelle vicinanze');
  expect(weather('BCFG')).toBe('Nebbia a banchi');
  expect(weather('XXYY')).toBe('Fenomeno non riconosciuto (XXYY)');
  expect(weather('')).toBeNull();
  expect(weather(null)).toBeNull();
});
