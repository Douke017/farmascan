import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { InventoryItem } from '../models/inventory.model';

@Injectable({ providedIn: 'root' })
export class InventoryService {
  private readonly base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  /**
   * Search inventory by the LPN barcode code scanned by the Zebra device.
   * GET /inventory/search/{lpn_code}
   */
  searchByLPN(lpnCode: string): Observable<InventoryItem> {
    const encoded = encodeURIComponent(lpnCode.trim().toUpperCase());
    return this.http.get<InventoryItem>(`${this.base}/inventory/search/${encoded}`);
  }
}
