import {
  Component, ChangeDetectionStrategy, ChangeDetectorRef, signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { HttpEventType } from '@angular/common/http';
import { UploadService } from '../../core/services/upload.service';
import { ProcessingJob } from '../../core/models/inventory.model';

type UploadState = 'idle' | 'uploading' | 'processing' | 'done' | 'error';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './upload.component.html',
  styleUrl: './upload.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UploadComponent {
  state: UploadState = 'idle';
  uploadProgress = 0;
  job: ProcessingJob | null = null;
  errorMessage = '';
  selectedFile: File | null = null;
  isDragging = false;

  readonly allowedExtensions = ['.xlsx', '.xls', '.csv'];

  constructor(
    private uploadService: UploadService,
    private cdr: ChangeDetectorRef
  ) {}

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = true;
    this.cdr.markForCheck();
  }

  onDragLeave(): void {
    this.isDragging = false;
    this.cdr.markForCheck();
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = false;
    const file = event.dataTransfer?.files?.[0];
    if (file) this.selectFile(file);
    this.cdr.markForCheck();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) this.selectFile(file);
  }

  selectFile(file: File): void {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!this.allowedExtensions.includes(ext)) {
      this.errorMessage = `Tipo de archivo no permitido: "${ext}". Use .xlsx, .xls o .csv`;
      this.state = 'error';
      this.cdr.markForCheck();
      return;
    }
    this.selectedFile = file;
    this.state = 'idle';
    this.errorMessage = '';
    this.cdr.markForCheck();
  }

  upload(): void {
    if (!this.selectedFile) return;

    this.state = 'uploading';
    this.uploadProgress = 0;
    this.job = null;

    this.uploadService.uploadFile(this.selectedFile).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress && event.total) {
          this.uploadProgress = Math.round((100 * event.loaded) / event.total);
          this.cdr.markForCheck();
        } else if (event.type === HttpEventType.Response && event.body) {
          const jobId = event.body.job_id;
          this.state = 'processing';
          this.cdr.markForCheck();
          this.pollJob(jobId);
        }
      },
      error: (err) => {
        this.state = 'error';
        this.errorMessage =
          err.error?.detail ?? 'Error al subir el archivo. Intente de nuevo.';
        this.cdr.markForCheck();
      },
    });
  }

  private pollJob(jobId: string): void {
    this.uploadService.pollJobStatus(jobId).subscribe({
      next: (job) => {
        this.job = job;
        if (job.status === 'completed' || job.status === 'failed') {
          this.state = job.status === 'completed' ? 'done' : 'error';
          if (job.status === 'failed') {
            this.errorMessage = job.error_message ?? 'Error procesando el archivo.';
          }
        }
        this.cdr.markForCheck();
      },
      error: () => {
        this.state = 'error';
        this.errorMessage = 'Error consultando el estado del procesamiento.';
        this.cdr.markForCheck();
      },
    });
  }

  reset(): void {
    this.state = 'idle';
    this.selectedFile = null;
    this.uploadProgress = 0;
    this.job = null;
    this.errorMessage = '';
    this.cdr.markForCheck();
  }

  formatBytes(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 ** 2) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 ** 2).toFixed(1) + ' MB';
  }
}
