// Which colour layers a sky symbol has. Kept apart from sprite.ts so the islands
// can ask without bundling the drawings, which only the build needs.

export const sunLayer = (base: string) => base.includes('-day') || base === 'thunder';
export const inkLayer = (base: string) => base !== 'clear-day';
