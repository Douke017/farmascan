import {
  Component, OnInit, OnDestroy, AfterViewChecked,
  ViewChild, ElementRef, HostListener,
  ChangeDetectionStrategy, ChangeDetectorRef
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
export class ScannerComponent implements OnInit, AfterViewChecked, OnDestroy {
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
  /** Set to true whenever we need to re-focus the input on the next view check. */
  private needsFocus = false;

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

  /**
   * Called after every view check. Moves focus back to the input as soon as
   * Angular finishes re-rendering (e.g. after @if shows/hides the result card).
   * This prevents the Zebra scanner from sending keystrokes to Chrome's address
   * bar when the DOM changes and focus is momentarily lost.
   */
  ngAfterViewChecked(): void {
    if (this.needsFocus) {
      this.needsFocus = false;
      this.lpnInputRef?.nativeElement?.focus();
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  // ─── Auto-focus after result or on blur ─────────────────────────────────
  focusInput(): void {
    // Schedule via ngAfterViewChecked so focus happens AFTER Angular finishes
    // rendering (avoids race condition with @if adding/removing DOM nodes).
    this.needsFocus = true;
  }

  /**
   * Global keydown interceptor — runs on every key press anywhere in the page.
   * If a Zebra scanner sends keystrokes while the input doesn't have focus
   * (e.g. Chrome address bar got it during a DOM re-render), this captures
   * printable characters and Enter and routes them to our input, preventing
   * the browser from navigating away.
   */
  @HostListener('document:keydown', ['$event'])
  onDocumentKeydown(event: KeyboardEvent): void {
    const active = document.activeElement;
    const input = this.lpnInputRef?.nativeElement;
    if (!input) return;

    // If focus is already on our input, let onKeydown handle it normally.
    if (active === input) return;

    // Ignore modifier-only keys and browser shortcuts (Ctrl+*, Alt+*, F-keys, Tab).
    if (event.ctrlKey || event.altKey || event.metaKey) return;
    if (event.key === 'Tab' || event.key.startsWith('F')) return;

    if (event.key === 'Enter') {
      // Prevent Chrome from acting on Enter (e.g. activating focused link/button).
      event.preventDefault();
      input.focus();
      const code = this.lpnInput.trim();
      if (code.length >= 3) {
        this.performSearch(code);
      }
      return;
    }

    // For printable characters: redirect focus to input and let the keystroke land.
    if (event.key.length === 1) {
      event.preventDefault();
      input.focus();
      // Manually append the character so it isn't lost.
      this.lpnInput += event.key;
      this.cdr.markForCheck();
      // Feed through debounced search (manual typing path).
      this.searchSubject.next(this.lpnInput);
    }
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
