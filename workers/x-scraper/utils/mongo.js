import mongoose from 'mongoose';
import { TweetSchema } from './tweetSchema.js';

export const TweetModel = mongoose.model('Tweet', TweetSchema);

export async function saveTweets(tweets, targetUser) {
  if (!tweets || tweets.length === 0) return;

  const operations = tweets.map(tweet => ({
    updateOne: {
      filter: { post_id: tweet.post_id },
      update: {
        $set: {
          user: targetUser,
          post_link: `https://x.com/${targetUser}/status/${tweet.post_id}`,
          text: tweet.text,
          post_time: new Date(tweet.post_time || tweet.created_at),
          likes: tweet.likes || tweet.favorite_count,
          total_comments: tweet.total_comments || tweet.reply_count,
          reposts: tweet.reposts || tweet.retweet_count,
          quotes: tweet.quotes || tweet.quote_count,
          comments: tweet.comments || [],
        },
      },
      upsert: true,
    }
  }));

  try {
    const result = await TweetModel.bulkWrite(operations, { ordered: false });
    console.log(`📥 MongoDB upserted: ${result.upsertedCount} new, ${result.modifiedCount} updated`);
  } catch (err) {
    console.error('❌ MongoDB upsert failed:', err.message);
  }
}
