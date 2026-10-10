package stats

import (
	"errors"
	"math"
	"testing"
)

func rankSlicesClose(got, want []float64, tol float64) bool {
	if len(got) != len(want) {
		return false
	}
	for i := range got {
		if math.IsNaN(got[i]) && math.IsNaN(want[i]) {
			continue
		}
		if math.Abs(got[i]-want[i]) > tol {
			return false
		}
	}
	return true
}

func TestRank(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{
			name:    "empty input",
			input:   Float64Data{},
			want:    nil,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "basic ranking with ties",
			input:   Float64Data{10, 20, 20, 30},
			want:    []float64{1, 2.5, 2.5, 4},
			wantErr: nil,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Rank(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !rankSlicesClose(got, tc.want, 1e-9) {
					t.Fatalf("expected ranks %v, got %v", tc.want, got)
				}
			}
		})
	}
}

func TestFloat64Data_Rank_Empty(t *testing.T) {
	var data Float64Data
	got, err := data.Rank()
	if err == nil {
		t.Fatalf("expected error for empty input, got nil")
	}
	if !errors.Is(err, ErrEmptyInput) {
		t.Errorf("expected ErrEmptyInput, got %v", err)
	}
	if got != nil {
		t.Errorf("expected nil slice for empty input, got %v", got)
	}
}

func TestFloat64Data_Rank_Basic(t *testing.T) {
	data := Float64Data{10, 20, 15}
	got, err := data.Rank()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []float64{1, 3, 2}
	if !rankSlicesClose(got, want, 1e-9) {
		t.Errorf("rank mismatch: got %v, want %v", got, want)
	}
}

func TestFloat64Data_Rank_Ties(t *testing.T) {
	data := Float64Data{5, 1, 5, 3}
	got, err := data.Rank()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Expected ranks: 5 -> 3.5 (average of positions 3 and 4), 1 -> 1, 5 -> 3.5, 3 -> 2
	want := []float64{3.5, 1, 3.5, 2}
	if !rankSlicesClose(got, want, 1e-9) {
		t.Errorf("rank with ties mismatch: got %v, want %v", got, want)
	}
}
