import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import Icons from 'unplugin-icons/vite';
// https://vite.dev/config/
export default defineConfig({
    plugins: [
        svelte(),
        Icons({
            compiler: 'svelte'
        })
    ],
    resolve: {
        alias: {
            '$lib': '/src/lib'
        }
    }
});
