import { Injectable } from '@angular/core';
import { HttpClient, HttpEvent, HttpRequest } from '@angular/common/http';
import { Observable, interval, switchMap, takeWhile, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ProcessingJob, UploadInitiated } from '../models/inventory.model';

@Injectable({ providedIn: 'root' })
export class UploadService {
  private readonly base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  /**
   * Upload an inventory file (xlsx or csv).
   * Returns an Observable with upload progress events.
   */
  uploadFile(file: File): Observable<HttpEvent<UploadInitiated>> {
    const formData = new FormData();
    formData.append('file', file);

    const req = new HttpRequest('POST', `${this.base}/inventory/upload`, formData, {
      reportProgress: true,
    });

    return this.http.request<UploadInitiated>(req);
  }

  /**
   * Poll job status every 2 seconds until completed or failed.
   */
  pollJobStatus(jobId: string): Observable<ProcessingJob> {
    return interval(2000).pipe(
      switchMap(() =>
        this.http.get<ProcessingJob>(`${this.base}/inventory/upload/jobs/${jobId}`)
      ),
      takeWhile(
        (job) => job.status !== 'completed' && job.status !== 'failed',
        true // emit the final value too
      )
    );
  }
}
