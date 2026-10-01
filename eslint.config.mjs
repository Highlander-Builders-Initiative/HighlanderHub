import nextVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  ...nextVitals,
  { ignores: ["**/.venv/**", ".release-private/**"] },
];

export default eslintConfig;
