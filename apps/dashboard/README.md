# Konozy AI Dashboard

Next.js frontend dashboard for Konozy AI Enterprise Order Management System.

## Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **API:** FastAPI Backend (http://localhost:8000)

## Setup

1. **Install dependencies:**
   ```bash
   cd apps/dashboard
   npm install
   # or
   yarn install
   ```

2. **Run development server:**
   ```bash
   npm run dev
   # or
   yarn dev
   ```

3. **Open browser:**
   Navigate to http://localhost:3000

## Environment Variables

Create `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Features

- **Orders Table:** View all orders with order number, store, status, total, and date
- **Sync Button:** Sync Amazon orders from SP-API
- **Dark/Light Mode:** Automatic theme based on system preferences
- **Responsive Design:** Works on desktop and mobile devices

## API Endpoints

The dashboard communicates with the FastAPI backend:

- `GET /api/v1/orders` - Fetch all orders
- `GET /api/v1/orders/{order_id}` - Fetch order by ID
- `POST /api/v1/marketplace/amazon/sync` - Sync Amazon orders
