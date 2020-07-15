import { values } from "lodash";

// The following colors will be used if you pick "Automatic" color
export const BaseColors = {
  "Life Green": "#05bf6f",
  "Cerulean Blue": "#12a1dc",
  "Coral Pink": "#eb5d66",
  "Earth Orange": "#f18b31",
  "Appleberry Mauve": "#574b99",
  "Sunrise Violet": "#c66aa6",
  "Sage Green": "#007965",
  "Warm Stone": "#726e6a",
  "Pale Stone": "#cfcbc8",
};

// Additional colors for the user to choose from
export const AdditionalColors = {
  "White": "#fafafa",
};

export const ColorPaletteArray = values(BaseColors);

const ColorPalette = {
  ...BaseColors,
  ...AdditionalColors,
};

export default ColorPalette;
