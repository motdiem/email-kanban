/**
 * Email Kanban Configuration
 *
 * Edit this file with your OAuth client IDs.
 * These are PUBLIC identifiers (not secrets) and are safe to use client-side.
 *
 * To get your client IDs:
 * - Microsoft: https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
 * - Google: https://console.cloud.google.com/apis/credentials
 * - TickTick: https://developer.ticktick.com/manage
 */

window.EMAIL_KANBAN_CONFIG = {
    microsoft: {
        clientId: 'YOUR_MICROSOFT_CLIENT_ID',
        authority: 'https://login.microsoftonline.com/organizations',
        redirectUri: window.location.origin + '/index.html',
        scopes: ['Mail.Read', 'Mail.ReadWrite', 'Mail.Read.Shared', 'Mail.ReadWrite.Shared']
    },
    google: {
        clientId: 'YOUR_GOOGLE_CLIENT_ID',
        scopes: ['https://www.googleapis.com/auth/gmail.modify']
    },
    ticktick: {
        clientId: '',  // Optional: Set default here or enter per-account in the app
        clientSecret: '',  // Optional: Set default here or enter per-account in the app
        redirectUri: window.location.origin + '/index.html',
        authUrl: 'https://ticktick.com/oauth/authorize',
        tokenUrl: 'https://ticktick.com/oauth/token',
        apiBase: 'https://api.ticktick.com/open/v1',
        scopes: ['tasks:read', 'tasks:write']
    }
};
