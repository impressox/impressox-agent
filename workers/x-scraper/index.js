import fs from 'fs';
import dotenv from 'dotenv';
dotenv.config();

import mongoose from 'mongoose';
import { initScraperWithCookies } from './utils/login.js';
import { getRotatingProxy } from './utils/proxyManager.js';
import { ProxyAgent, setGlobalDispatcher } from 'undici';
import { saveTweets } from './utils/mongo.js';
import pLimit from 'p-limit';

await mongoose.connect(process.env.MONGO_URI);

// Load account list
const accounts = fs.readFileSync('accounts/x-accounts.txt', 'utf-8')
    .trim()
    .split('\n')
    .map(line => {
        const [username, password, twofa] = line.split('|');
        return { username, password, twofa };
    });

// Load user target list
const users = fs.readFileSync('user_list.txt', 'utf-8').trim().split('\n');

// Divide users evenly across accounts
const chunkSize = Math.ceil(users.length / accounts.length);
const chunks = Array.from({ length: accounts.length }, (_, i) =>
    users.slice(i * chunkSize, (i + 1) * chunkSize)
);

// Core logic: fetch tweets (interface-based)
async function fetchTweets(scraper, username, userId, limit = 200) {
    const tweets = [];
    let page = null;

    while (true) {
        console.log(`🔄 [${username}] Fetching tweets...`);
        const proxyUrl = await getRotatingProxy();
        setGlobalDispatcher(new ProxyAgent(proxyUrl));
        page = await scraper.getUserTweets(userId, 100, page?.next);
        console.log(`🌐 [${username}] Fetched ${page?.tweets?.length || 0} tweets`);
        if (!page?.tweets?.length) break;

        for (const tweet of page.tweets) {
            if (!tweet.id) continue;

            const tweetData = {
                user: tweet.username || username,
                post_id: tweet.id,
                post_link: tweet.permanentUrl || `https://x.com/${tweet.username}/status/${tweet.id}`,
                text: tweet.text,
                post_time: tweet.timeParsed || (tweet.timestamp ? new Date(tweet.timestamp * 1000) : null),
                likes: tweet.likes || 0,
                total_comments: tweet.replies || 0,
                reposts: tweet.retweets || 0,
                quotes: tweet.quotedStatusId ? 1 : 0,
                comments: []  // will be populated in later enhancement
            };

            tweets.push(tweetData);
            console.log(`📝 [${username}] Fetched tweet ${tweet.id} (${tweets.length}/${limit})`);
            if (tweets.length >= limit) break;
        }

        if (!page.next || tweets.length >= limit) break;
    }

    return tweets;
}

// One crawl loop (all accounts, all users)

const USER_CONCURRENCY = 3;

async function runCrawl() {
    console.log(`\n⏱️ [${new Date().toLocaleString()}] Starting crawl...`);

    for (let i = 0; i < accounts.length; i++) {
        const account = accounts[i];
        const assignedUsers = chunks[i];

        try {
            const proxyUrl = await getRotatingProxy();
            setGlobalDispatcher(new ProxyAgent(proxyUrl));
            const scraper = await initScraperWithCookies(account);
            const limit = pLimit(USER_CONCURRENCY);

            const tasks = assignedUsers.map(username =>
                limit(async () => {
                    let retry = 0;
                    const maxRetries = 5;
                    while (retry < maxRetries) {
                        try {
                            const proxyUrl = await getRotatingProxy();
                            setGlobalDispatcher(new ProxyAgent(proxyUrl));
                            console.log(`🌐 [${account.username}] Using proxy ${proxyUrl} for ${username}`);

                            const userId = await scraper.getUserIdByScreenName(username);
                            const tweets = await fetchTweets(scraper, username, userId);
                            await saveTweets(tweets, username);
                            console.log(`✅ [${account.username}] Saved ${tweets.length} tweets from ${username}`);
                            break;
                        } catch (err) {
                            retry++;
                            console.error(`❌ [${account.username}] Failed ${username} (attempt ${retry}/5): ${err.message}`);
                            if (retry < maxRetries) {
                                console.log(`⏳ Waiting 10s before retrying ${username}...`);
                                await new Promise(r => setTimeout(r, 10000));
                            } else {
                                console.warn(`⚠️ Skipping ${username} after ${maxRetries} attempts.`);
                            }
                        }
                    }
                })
            );

            await Promise.allSettled(tasks);
        } catch (err) {
            console.error(`❌ Error logging in with account ${account.username}: ${err.message}`);
        }
    }

    console.log(`✅ Crawl completed at ${new Date().toLocaleString()}`);
}

// Loop every 5 minutes, sequential (no overlap)
async function startLoop() {
    while (true) {
        try {
            await runCrawl();
        } catch (err) {
            console.error(`❌ Error in crawl loop: ${err.message}`);
        }
        console.log(`⏳ Waiting 5 minutes before next crawl...\n`);
        await new Promise(resolve => setTimeout(resolve, 5 * 60 * 1000));
    }
}

await startLoop();
