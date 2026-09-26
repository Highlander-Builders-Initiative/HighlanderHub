import nextVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  ...nextVitals,
  { ignores: ["**/.venv/**"] },
];

export default eslintConfig;
