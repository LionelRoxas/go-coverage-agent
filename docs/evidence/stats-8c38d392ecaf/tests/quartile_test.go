package stats

import (
	"errors"
	"math"
	"testing"
)

func quartileApproxEqual(t *testing.T, got, want float64) {
	if math.IsNaN(got) && math.IsNaN(want) {
		return
	}
	if math.Abs(got-want) > 1e-9 {
		t.Errorf("got %v want %v", got, want)
	}
}

func TestQuartile(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    Quartiles
		wantErr bool
	}{
		{"empty", Float64Data{}, Quartiles{}, true},
		{"single", Float64Data{42}, Quartiles{}, true},
		{"even", Float64Data{1, 2, 3, 4}, Quartiles{1.5, 2.5, 3.5}, false},
		{"odd_unsorted", Float64Data{5, 1, 4, 2, 3}, Quartiles{1.5, 3, 4.5}, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Quartile(tc.input)
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
			quartileApproxEqual(t, got.Q1, tc.want.Q1)
			quartileApproxEqual(t, got.Q2, tc.want.Q2)
			quartileApproxEqual(t, got.Q3, tc.want.Q3)
		})
	}
}

func TestInterQuartileRange(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr bool
	}{
		{"empty", Float64Data{}, math.NaN(), true},
		{"even", Float64Data{1, 2, 3, 4}, 2.0, false},
		{"odd", Float64Data{5, 1, 4, 2, 3}, 3.0, false},
	}
	for _, tc := range cases {
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
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			quartileApproxEqual(t, got, tc.want)
		})
	}
}

func TestMidhinge(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr bool
	}{
		{"empty", Float64Data{}, math.NaN(), true},
		{"even", Float64Data{1, 2, 3, 4}, 2.5, false},
		{"odd", Float64Data{5, 1, 4, 2, 3}, 3.0, false},
	}
	for _, tc := range cases {
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
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			quartileApproxEqual(t, got, tc.want)
		})
	}
}

func TestTrimean(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr bool
	}{
		{"empty", Float64Data{}, math.NaN(), true},
		{"even", Float64Data{1, 2, 3, 4}, 2.5, false},
		{"odd", Float64Data{5, 1, 4, 2, 3}, 3.0, false},
	}
	for _, tc := range cases {
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
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			quartileApproxEqual(t, got, tc.want)
		})
	}
}
