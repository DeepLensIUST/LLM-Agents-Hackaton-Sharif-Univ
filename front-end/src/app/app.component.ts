import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import {MatButtonModule} from '@angular/material/button';
import {FormBuilder, FormsModule, ReactiveFormsModule} from '@angular/forms';
import {MatInputModule} from '@angular/material/input';
import {MatFormFieldModule} from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import {MatMenuModule} from '@angular/material/menu';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { CommonModule } from '@angular/common';
@Component({
  selector: 'app-root',
  imports: [
    MatCheckboxModule,
    MatMenuModule,
    RouterOutlet,
    MatInputModule,
    MatFormFieldModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    FormsModule, 
    ReactiveFormsModule,
    HttpClientModule,
    CommonModule 
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {
  title = 'Front';
  value = ' ';
  userPrompt= ' ';
  response: any = null;

  constructor(private http: HttpClient) {}

  private readonly _formBuilder = inject(FormBuilder);

  readonly toppings = this._formBuilder.group({
    run: false,
    debug: false,
    clean: false,
    forecast: false,
    tests: false,
  });

  selectAllAgents() {
  this.toppings.patchValue({
    run: true,
    debug: true,
    clean: true,
    forecast: true,
    tests: true
  });
}

  getRunKeys(): string[] {
  return this.response && this.response.run ? Object.keys(this.response.run) : [];
}

getTestRounds(): string[] {
  return this.response?.tests?.pytest_rounds
    ? Object.keys(this.response.tests.pytest_rounds)
    : [];
}


  submit() {
  console.log('click sumbied');
  const body = {
    code_request: {
      code: this.value,
      user_prompt : this.userPrompt,
      filename: "user.py"
    },
    agents: this.toppings.value  // ❗️ نکته مهم
  };
  console.log('body : ' , body)

  this.http.post('http://127.0.0.1:8000/analyze', body).subscribe({
    next: res => {
      console.log('body : ' , body)
      console.log('✅ Response from API:', res);
      // اینجا می‌تونی خروجی‌ها رو توی UI نشون بدی
      this.response = res;

    },
    error: err => {
      console.error('❌ API error:', err);
    }
  });
}

}
