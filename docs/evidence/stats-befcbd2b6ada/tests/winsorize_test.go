package stats

import (
	"errors"
	"math"
	"testing"
)

type winsorizeCase struct {
	name    string
	input   []float64
	percent float64
	want    []float64
	wantErr error
}

func winsorizeSlicesEqual(a, b []float64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func TestWinsorize(t *testing.T) {
	cases := []winsorizeCase{
		{
			name:    "empty input",
			input:   []float64{},
			percent: 0.1,
			want:    nil,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "percent negative",
			input:   []float64{1, 2, 3},
			percent: -0.1,
			want:    nil,
			wantErr: ErrBounds,
		},
		{
			name:    "percent too high",
			input:   []float64{1, 2, 3},
			percent: 0.5,
			want:    nil,
			wantErr: ErrBounds,
		},
		{
			name:    "percent NaN",
			input:   []float64{1, 2, 3},
			percent: math.NaN(),
			want:    nil,
			wantErr: ErrBounds,
		},
		{
			name:    "zero percent returns copy",
			input:   []float64{3, 1, 4, 1, 5},
			percent: 0,
			want:    []float64{3, 1, 4, 1, 5},
			wantErr: nil,
		},
		{
			name:    "normal percent clamps",
			input:   []float64{10, 2, 8, 4, 6},
			percent: 0.2,
			want:    []float64{8, 4, 8, 4, 6},
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			// keep a copy of input to verify it is not mutated
			orig := append([]float64(nil), tc.input...)
			got, err := Winsorize(tc.input, tc.percent)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if err != nil {
				return
			}
			if !winsorizeSlicesEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
			if !winsorizeSlicesEqual(tc.input, orig) {
				t.Errorf("input slice was modified")
			}
		})
	}
}

func TestFloat64Data_Winsorize(t *testing.T) {
	// normal case forwarding
	data := Float64Data{10, 2, 8, 4, 6}
	got, err := data.Winsorize(0.2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []float64{8, 4, 8, 4, 6}
	if !winsorizeSlicesEqual(got, want) {
		t.Fatalf("expected %v, got %v", want, got)
	}

	// empty input forwarding
	empty := Float64Data{}
	_, err = empty.Winsorize(0.1)
	if !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
}
