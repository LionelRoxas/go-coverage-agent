package stats

import (
	"errors"
	"math"
	"testing"
)

func TestQuartile_Errors(t *testing.T) {
	tests := []struct {
		name  string
		input Float64Data
	}{
		{"empty", Float64Data{}},
		{"single", Float64Data{42}},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := Quartile(tc.input)
			if err == nil {
				t.Fatalf("expected error, got nil")
			}
			if !errors.Is(err, EmptyInputErr) {
				t.Fatalf("expected EmptyInputErr, got %v", err)
			}
		})
	}
}

func TestInterQuartileRange(t *testing.T) {
	tests := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr bool
	}{
		{"even", Float64Data{1, 2, 3, 4}, 2.0, false},
		{"odd", Float64Data{1, 2, 3, 4, 5}, 3.0, false},
		{"error", Float64Data{7}, 0, true},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := InterQuartileRange(tc.input)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, EmptyInputErr) {
					t.Fatalf("expected EmptyInputErr, got %v", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("iqr mismatch: got %v want %v", got, tc.want)
			}
		})
	}
}

func TestMidhinge(t *testing.T) {
	tests := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr bool
	}{
		{"even", Float64Data{1, 2, 3, 4}, 2.5, false},
		{"odd", Float64Data{1, 2, 3, 4, 5}, 3.0, false},
		{"error", Float64Data{}, 0, true},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Midhinge(tc.input)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, EmptyInputErr) {
					t.Fatalf("expected EmptyInputErr, got %v", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("midhinge mismatch: got %v want %v", got, tc.want)
			}
		})
	}
}

func TestTrimean(t *testing.T) {
	tests := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr bool
	}{
		{"even", Float64Data{1, 2, 3, 4}, 2.5, false},
		{"odd", Float64Data{1, 2, 3, 4, 5}, 3.0, false},
		{"error", Float64Data{9}, 0, true},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Trimean(tc.input)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, EmptyInputErr) {
					t.Fatalf("expected EmptyInputErr, got %v", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("trimean mismatch: got %v want %v", got, tc.want)
			}
		})
	}
}
