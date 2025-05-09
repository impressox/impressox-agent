import fs from 'fs';
import path from 'path';
import { Scraper } from 'agent-twitter-client';
import { Cookie } from 'tough-cookie';
const COOKIE_DIR = './cookies';
// 🧩 Helper: Load cookies from file
function loadCookiesForUser(username) {
    const cookiePath = path.resolve(`${COOKIE_DIR}/${username}.json`);
    if (!fs.existsSync(cookiePath)) return null;

    try {
        const cookiesData = fs.readFileSync(cookiePath, 'utf8');
        const rawCookies = JSON.parse(cookiesData);
        return rawCookies.map(cookieData => Cookie.fromJSON(cookieData));
    } catch (error) {
        console.error(`❌ Error loading cookies for ${username}:`, error.message);
        return null;
    }
}

// 🧩 Helper: Save cookies to file
function saveCookiesForUser(username, cookies) {
    try {
        const cookiePath = path.resolve(`${COOKIE_DIR}/${username}.json`);
        fs.mkdirSync(COOKIE_DIR, { recursive: true });
        const cookiesData = cookies.map(cookie => cookie.toJSON());
        fs.writeFileSync(cookiePath, JSON.stringify(cookiesData, null, 2));
        console.log(`✅ Cookies saved for ${username}`);
    } catch (err) {
        console.error(`❌ Error saving cookies for ${username}:`, err.message);
    }
}

// 🚀 Main init function with cookie handling
export async function initScraperWithCookies(account) {
    const scraper = new Scraper();

    const savedCookies = loadCookiesForUser(account.username);
    if (savedCookies) {
        try {
            const cookieStrings = savedCookies.map(cookie => cookie.toString()); 
            await scraper.setCookies(cookieStrings);
            const loggedIn = await scraper.isLoggedIn();
            if (loggedIn) {
                console.log(`✅ [${account.username}] Logged in using saved cookies.`);
                return scraper;
            } else {
                console.warn(`⚠️ [${account.username}] Cookies invalid, fallback to login.`);
            }
        } catch (e) {
            console.warn(`⚠️ Failed to set cookies for ${account.username}: ${e.message}`);
        }
    }

    // 🔐 Login mới nếu cookies không dùng được
    try {
        await scraper.login(
            account.username,
            account.password,
            "",
            account.twofa
        );

        const cookies = await scraper.getCookies();
        saveCookiesForUser(account.username, cookies);
        console.log(`✅ [${account.username}] Logged in and saved new cookies.`);
        return scraper;
    } catch (err) {
        throw new Error(`❌ Login failed for ${account.username}: ${err.message}`);
    }
}
