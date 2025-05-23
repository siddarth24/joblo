# Use an official Node.js runtime as a parent image
# Choose a version compatible with your Next.js project (e.g., LTS version)
FROM node:18-alpine

# Set the working directory in the container
WORKDIR /app/frontend

# Copy package.json and package-lock.json (or yarn.lock) first
# This leverages Docker cache. If these files don't change, Docker won't re-run npm install.
COPY package*.json ./
# If using yarn, uncomment the next two lines and comment out the npm ci line
# COPY yarn.lock ./
# RUN yarn install --frozen-lockfile

# Install dependencies using npm ci for cleaner installs from package-lock.json
RUN npm ci

# Copy the rest of the frontend application code into the container
COPY . .

# Make port 3000 available to the world outside this container
EXPOSE 3000

# Define the command to run the Next.js development server
CMD ["npm", "run", "dev"] 