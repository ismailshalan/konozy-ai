'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import { orderClient, SyncResponse } from '@/lib/api';

export default function SyncButton() {
  const [isLoading, setIsLoading] = useState(false);

  const handleSync = async () => {
    setIsLoading(true);

    try {
      const response: SyncResponse = await orderClient.syncAmazonOrders();
      
      toast.success(`Successfully synced ${response.orders_synced} orders`, {
        description: 'Orders have been synchronized from Amazon SP-API',
        duration: 4000,
      });
      
      // Refresh the page after a short delay to show updated data
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to sync orders';
      toast.error('Sync Failed', {
        description: errorMessage,
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <button
      onClick={handleSync}
      disabled={isLoading}
      className={`
        px-4 py-2 rounded-lg font-medium transition-colors
        ${isLoading
          ? 'bg-gray-400 cursor-not-allowed text-white'
          : 'bg-blue-600 hover:bg-blue-700 text-white'
        }
      `}
    >
      {isLoading ? (
        <span className="flex items-center gap-2">
          <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          Syncing...
        </span>
      ) : (
        'Sync Amazon Orders'
      )}
    </button>
  );
}
