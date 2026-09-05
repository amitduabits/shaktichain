export const SEED_VEHICLES = [
  { id: 'veh-1', name: 'Home EV', city: 'Delhi', capacityKwh: 60, soc: 0.72 },
  { id: 'veh-2', name: 'Depot van 1', city: 'Mumbai', capacityKwh: 80, soc: 0.54 },
  { id: 'veh-3', name: 'Depot van 2', city: 'Bangalore', capacityKwh: 80, soc: 0.61 },
  { id: 'veh-4', name: 'Fleet sedan', city: 'Chennai', capacityKwh: 55, soc: 0.48 },
  { id: 'veh-5', name: 'Reserve EV', city: 'Kolkata', capacityKwh: 70, soc: 0.81 },
];

export const SEED_SITES = [
  { id: 'site-1', name: 'CP-Delhi Hub', city: 'Delhi', chargers: 12, kwhToday: 840, occupancy: 0.62 },
  { id: 'site-2', name: 'CP-Mumbai East', city: 'Mumbai', chargers: 8, kwhToday: 510, occupancy: 0.44 },
  { id: 'site-3', name: 'CP-Bengaluru Tech', city: 'Bangalore', chargers: 16, kwhToday: 1200, occupancy: 0.71 },
];

export const SEED_FEEDERS = [
  { id: 'fd-1', name: 'DL-F12', city: 'Delhi', hostingKw: 4200, curtailmentPct: 0.12 },
  { id: 'fd-2', name: 'MU-F04', city: 'Mumbai', hostingKw: 3800, curtailmentPct: 0.08 },
  { id: 'fd-3', name: 'BL-F09', city: 'Bangalore', hostingKw: 5100, curtailmentPct: 0.21 },
  { id: 'fd-4', name: 'KK-F02', city: 'Kolkata', hostingKw: 2900, curtailmentPct: 0.05 },
];

export const SEED_PORTFOLIO = {
  residential: 50,
  commercial: 30,
  fleet: 20,
};

export function createRoleFixtures() {
  return {
    vehicles: SEED_VEHICLES.map((row) => ({ ...row })),
    sites: SEED_SITES.map((row) => ({ ...row })),
    feeders: SEED_FEEDERS.map((row) => ({ ...row })),
    portfolio: { ...SEED_PORTFOLIO },
  };
}
