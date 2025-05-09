FROM node:22

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Create required directories
RUN mkdir -p accounts cookies

# Run the app
CMD ["node", "index.js"]
