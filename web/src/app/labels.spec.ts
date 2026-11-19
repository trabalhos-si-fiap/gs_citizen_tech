import { toDateTimeLocal } from './labels';

describe('toDateTimeLocal', () => {
  it('formata no fuso local, como o input datetime-local espera', () => {
    // Construída com componentes locais: o resultado não pode depender do UTC.
    const date = new Date(2026, 10, 19, 9, 5, 42);

    expect(toDateTimeLocal(date)).toBe('2026-11-19T09:05');
  });

  it('não desloca pelo offset do fuso (toISOString usaria UTC)', () => {
    const date = new Date(2026, 0, 1, 23, 30);

    expect(toDateTimeLocal(date)).toBe('2026-01-01T23:30');
  });
});
