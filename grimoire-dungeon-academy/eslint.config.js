import js from '@eslint/js';
import globals from 'globals';
export default [js.configs.recommended,{files:['**/*.js','**/*.mjs'],languageOptions:{ecmaVersion:'latest',sourceType:'module',globals:{...globals.browser,...globals.node,...globals.serviceworker}},rules:{'no-unused-vars':['error',{argsIgnorePattern:'^_'}],'no-constant-condition':['error',{checkLoops:false}]}},{ignores:['dist/**','node_modules/**','public/**']}];
