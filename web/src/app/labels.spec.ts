import { coordinatesLabel, formatDateTime, locationLabel, toDateTimeLocal } from './labels';

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

describe('locationLabel', () => {
  const point = { lat: -23.573806, lon: -46.623157 };

  it('mostra o endereço enviado pelo app quando existe', () => {
    expect(locationLabel({ ...point, address: 'Rua Exemplo, 123 – Bairro, Cidade' })).toBe(
      'Rua Exemplo, 123 – Bairro, Cidade',
    );
  });

  it('usa as coordenadas nos reportes antigos, sem endereço', () => {
    expect(locationLabel({ ...point, address: null })).toBe('-23.5738, -46.6232');
  });

  it('trata endereço em branco como ausente', () => {
    expect(locationLabel({ ...point, address: '   ' })).toBe('-23.5738, -46.6232');
  });

  it('aceita a precisão das coordenadas do detalhe', () => {
    expect(locationLabel({ ...point, address: null }, 5)).toBe('-23.57381, -46.62316');
  });
});

describe('coordinatesLabel', () => {
  it('formata latitude e longitude com 4 casas por padrão', () => {
    expect(coordinatesLabel(-23.573806, -46.623157)).toBe('-23.5738, -46.6232');
  });
});

describe('formatDateTime', () => {
  // A API passou a devolver as datas com fuso (UTC); o resultado não muda.
  it('lê datas em UTC com Z ou +00:00 como o formato antigo sem fuso', () => {
    const legacy = formatDateTime('2026-11-19T23:29:25.789511');

    expect(formatDateTime('2026-11-19T23:29:25.789511Z')).toBe(legacy);
    expect(formatDateTime('2026-11-19T23:29:25.789511+00:00')).toBe(legacy);
    expect(legacy).not.toContain('Invalid');
  });
});
