import mongoose from 'mongoose';

export const TweetSchema = new mongoose.Schema({
  user: { type: String, required: true },
  post_id: { type: Number, required: true, unique: true },
  post_link: { type: String },
  text: { type: String },
  post_time: { type: Date },
  likes: { type: Number, default: 0 },
  total_comments: { type: Number, default: 0 },
  reposts: { type: Number, default: 0 },
  quotes: { type: Number, default: 0 },
  comments: [
    {
      comment_id: { type: Number },
      original_comment_id: { type: String },
      user: { type: String },
      text: { type: String },
      timestamp: { type: Date },
      likes: { type: Number, default: 0 },
      reposts: { type: Number, default: 0 },
      quotes: { type: Number, default: 0 }
    }
  ]
});
