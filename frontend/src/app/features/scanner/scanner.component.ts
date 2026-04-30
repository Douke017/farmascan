import {
  Component, OnInit, OnDestroy, ViewChild, ElementRef,
  ChangeDetectionStrategy, ChangeDetectorRef, signal, computed
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { Subject, debounceTime, takeUntil } from 'rxjs';
import { InventoryService } from '../../core/services/inventory.service';
import { InventoryItem } from '../../core/models/inventory.model';

type ScanState = 'idle' | 'scanning' | 'found' | 'not-found' | 'error';

@Component({
  selector: 'app-scanner',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './scanner.component.html',
  styleUrl: './scanner.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ScannerComponent implements OnInit, OnDestroy {
  @ViewChild('lpnInputRef') lpnInputRef!: ElementRef<HTMLInputElement>;

  // ─── State ──────────────────────────────────────────────────────────────
  lpnInput = '';
  state: ScanState = 'idle';
  result: InventoryItem | null = null;
  errorMessage = '';

  // ─── Barcode scanner detection ──────────────────────────────────────────
  // Zebra DataWedge sends keystrokes very fast; we detect this timing
  private lastKeyTime = 0;
  private keyBuffer = '';
  private readonly SCAN_SPEED_THRESHOLD_MS = 50; // chars faster than 50ms = scanner
  private readonly SCAN_MIN_LENGTH = 6;
  private searchSubject = new Subject<string>();
  private destroy$ = new Subject<void>();

  constructor(
    private inventoryService: InventoryService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    // Debounce manual typing (400ms); scanner input arrives near-instantly
    this.searchSubject
      .pipe(debounceTime(400), takeUntil(this.destroy$))
      .subscribe((lpn) => {
        if (lpn.trim().length >= 3) {
          this.performSearch(lpn.trim());
        }
      });
  }

  ngAfterViewInit(): void {
    this.focusInput();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  // ─── Auto-focus after result or on blur ─────────────────────────────────
  focusInput(): void {
    setTimeout(() => this.lpnInputRef?.nativeElement?.focus(), 100);
  }

  // ─── Key events — barcode scan detection ─────────────────────────────────
  onKeydown(event: KeyboardEvent): void {
    const now = Date.now();
    const timeDelta = now - this.lastKeyTime;
    this.lastKeyTime = now;

    if (event.key === 'Enter') {
      event.preventDefault();
      const code = this.lpnInput.trim();
      if (code.length >= 3) {
        this.performSearch(code);
      }
      return;
    }

    // Detect scanner: keystrokes arriving faster than threshold
    if (timeDelta < this.SCAN_SPEED_THRESHOLD_MS && event.key.length === 1) {
      this.keyBuffer += event.key;
      // If buffer reaches meaningful length + no more keys expected, search
      if (this.keyBuffer.length >= this.SCAN_MIN_LENGTH) {
        clearTimeout((this as any)._scanTimeout);
        (this as any)._scanTimeout = setTimeout(() => {
          if (this.keyBuffer.length >= this.SCAN_MIN_LENGTH) {
            this.performSearch(this.keyBuffer);
            this.keyBuffer = '';
          }
        }, 80); // 80ms silence = scan complete
      }
    } else {
      this.keyBuffer = event.key.length === 1 ? event.key : '';
    }
  }

  onInput(): void {
    this.searchSubject.next(this.lpnInput);
  }

  onClear(): void {
    this.lpnInput = '';
    this.state = 'idle';
    this.result = null;
    this.errorMessage = '';
    this.keyBuffer = '';
    this.cdr.markForCheck();
    this.focusInput();
  }

  // ─── Search ─────────────────────────────────────────────────────────────
  performSearch(lpnCode: string): void {
    if (this.state === 'scanning') return;

    this.state = 'scanning';
    this.result = null;
    this.errorMessage = '';
    this.lpnInput = lpnCode;
    this.cdr.markForCheck();

    this.inventoryService.searchByLPN(lpnCode).subscribe({
      next: (item) => {
        this.result = item;
        this.state = 'found';
        this.cdr.markForCheck();
        // Re-focus for next scan
        this.focusInput();
      },
      error: (err: HttpErrorResponse) => {
        if (err.status === 404) {
          this.state = 'not-found';
          this.errorMessage = `LPN "${lpnCode}" no encontrado en el inventario.`;
        } else {
          this.state = 'error';
          this.errorMessage = 'Error de conexión con el servidor.';
        }
        this.cdr.markForCheck();
        this.focusInput();
      },
    });
  }

  // ─── Template helpers ────────────────────────────────────────────────────
  getStatusClass(estado: string): string {
    const lower = estado.toLowerCase();
    if (lower.includes('ubicado') && !lower.includes('parcial')) return 'ubicado';
    if (lower.includes('parcial')) return 'parcial';
    if (lower.includes('asignado')) return 'asignado';
    return 'default';
  }

  getStatusIcon(estado: string): string {
    const lower = estado.toLowerCase();
    if (lower.includes('ubicado') && !lower.includes('parcial')) return '✓';
    if (lower.includes('parcial')) return '◑';
    if (lower.includes('asignado')) return '⬤';
    return '?';
  }

  getCurvaClass(curva: string): string {
    return ['A', 'B', 'C'].includes(curva.toUpperCase()) ? curva.toUpperCase() : '0';
  }
}
