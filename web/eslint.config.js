import { defineConfig } from "eslint/config";
import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

/**
 * R1, read off typescript-eslint 8.69.0's own rule schema rather than assumed by name:
 * `switch-exhaustiveness-check` reports `dangerousDefaultCase` only when
 * `allowDefaultCaseForExhaustiveSwitch` is false, and counts a `default` arm as handling a new
 * union member unless `considerDefaultExhaustiveForUnions` is false. Both are needed: the first
 * forbids the arm, the second stops it standing in for a member. Defaults are the wrong way
 * round for FR-004 on the first, so it is set here explicitly.
 */
const EXHAUSTIVENESS_RULE = "@typescript-eslint/switch-exhaustiveness-check";
const EXHAUSTIVENESS_OPTIONS = {
  allowDefaultCaseForExhaustiveSwitch: false,
  considerDefaultExhaustiveForUnions: false,
  requireDefaultForNonUnion: false,
};

/** FR-021a: the module allowed to read a clock, and the only one. */
const CLOCK_MODULE = "src/clock.ts";

const CLOCK_SELECTORS = [
  {
    selector: "NewExpression[callee.name='Date']",
    message:
      "FR-021a: the client reads a clock once, in src/clock.ts. A second read is how the `as_of` in the URL and the date a figure was aged at come to disagree.",
  },
  {
    selector: "CallExpression[callee.object.name='Date'][callee.property.name='now']",
    message:
      "FR-021a: the client reads a clock once, in src/clock.ts. A second read is how the `as_of` in the URL and the date a figure was aged at come to disagree.",
  },
];

/**
 * FR-005: a cast is FR-004 switched off at one site. `as const` is not one -- it widens nothing
 * and asserts nothing about a response.
 */
const CAST_SELECTORS = [
  {
    selector: "TSAsExpression[typeAnnotation.typeName.name!='const']",
    message: "FR-005: no cast over a response type. Narrow with a type predicate instead.",
  },
  {
    selector: "TSTypeAssertion",
    message: "FR-005: no cast over a response type. Narrow with a type predicate instead.",
  },
];

export default defineConfig(
  {
    // `.union-widening` is a copy of `src` a test makes and removes; a killed run leaves it, and
    // the gate would then fail on files no tsconfig includes.
    ignores: [
      "dist",
      "node_modules",
      "src/api/schema.d.ts",
      "playwright-report",
      "test-results",
      ".union-widening",
    ],
  },
  js.configs.recommended,
  tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      globals: { ...globals.browser },
      parserOptions: {
        projectService: { allowDefaultProject: ["eslint.config.js", "tools/*.mjs"] },
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      [EXHAUSTIVENESS_RULE]: ["error", EXHAUSTIVENESS_OPTIONS],
      // FR-005's other half: a cast is FR-004 switched off at one site.
      "@typescript-eslint/consistent-type-assertions": [
        "error",
        { assertionStyle: "never" },
      ],
      "@typescript-eslint/no-non-null-assertion": "error",
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: [CLOCK_MODULE],
    rules: { "no-restricted-syntax": ["error", ...CLOCK_SELECTORS, ...CAST_SELECTORS] },
  },
  {
    // The router's redirect is a thrown control-flow value by its own contract, and a route that
    // returned it instead would render the page it is redirecting away from.
    files: ["src/routes/**/*.tsx"],
    rules: { "@typescript-eslint/only-throw-error": "off" },
  },
  {
    files: ["tests/**/*.{ts,tsx}", "e2e/**/*.ts", "*.config.ts", "eslint.config.js", "tools/*.mjs"],
    languageOptions: { globals: { ...globals.node } },
    rules: {
      // A test reads what the runtime actually produced, so the shapes it handles are wider than
      // the ones the types promise -- which is the point of the assertion.
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/no-unsafe-call": "off",
      "@typescript-eslint/no-unnecessary-condition": "off",
    },
  },
);
