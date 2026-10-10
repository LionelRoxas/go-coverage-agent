package stats

import (
	"math"
	"testing"
)

type extremesCase struct {
	name    string
	data    []float64
	wantIdx int
	wantErr error
	wantVal float64 // for Range tests
}

func TestArgMax(t *testing.T) {
	cases := []extremesCase{{
		name:    "empty",
		data:    []float64{},
		wantIdx: -1,
		wantErr: ErrEmptyInput,
	}, {
		name:    "single",
		data:    []float64{42},
		wantIdx: 0,
		wantErr: nil,
	}, {
		name:    "multiple distinct",
		data:    []float64{1, 5, 3, 4},
		wantIdx: 1,
		wantErr: nil,
	}, {
		name:    "tie first occurrence",
		data:    []float64{2, 7, 7, 5},
		wantIdx: 1,
		wantErr: nil,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			idx, err := ArgMax(Float64Data(tc.data))
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if idx != tc.wantIdx {
					t.Fatalf("expected index %d, got %d", tc.wantIdx, idx)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if idx != tc.wantIdx {
				t.Fatalf("expected index %d, got %d", tc.wantIdx, idx)
			}
		})
	}
}

func TestArgMin(t *testing.T) {
	cases := []extremesCase{{
		name:    "empty",
		data:    []float64{},
		wantIdx: -1,
		wantErr: ErrEmptyInput,
	}, {
		name:    "single",
		data:    []float64{-3},
		wantIdx: 0,
		wantErr: nil,
	}, {
		name:    "multiple distinct",
		data:    []float64{5, 2, 8, 4},
		wantIdx: 1,
		wantErr: nil,
	}, {
		name:    "tie first occurrence",
		data:    []float64{6, 1, 1, 9},
		wantIdx: 1,
		wantErr: nil,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			idx, err := ArgMin(Float64Data(tc.data))
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if idx != tc.wantIdx {
					t.Fatalf("expected index %d, got %d", tc.wantIdx, idx)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if idx != tc.wantIdx {
				t.Fatalf("expected index %d, got %d", tc.wantIdx, idx)
			}
		})
	}
}

func TestFloat64Data_ArgMax(t *testing.T) {
	// Reuse cases from ArgMax test to ensure method forwards correctly
	cases := []extremesCase{{
		name:    "empty",
		data:    []float64{},
		wantIdx: -1,
		wantErr: ErrEmptyInput,
	}, {
		name:    "multiple with tie",
		data:    []float64{3, 9, 9, 2},
		wantIdx: 1,
		wantErr: nil,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			idx, err := Float64Data(tc.data).ArgMax()
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if idx != tc.wantIdx {
					t.Fatalf("expected index %d, got %d", tc.wantIdx, idx)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if idx != tc.wantIdx {
				t.Fatalf("expected index %d, got %d", tc.wantIdx, idx)
			}
		})
	}
}

func TestFloat64Data_ArgMin(t *testing.T) {
	cases := []extremesCase{{
		name:    "empty",
		data:    []float64{},
		wantIdx: -1,
		wantErr: ErrEmptyInput,
	}, {
		name:    "multiple with tie",
		data:    []float64{7, 2, 2, 5},
		wantIdx: 1,
		wantErr: nil,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			idx, err := Float64Data(tc.data).ArgMin()
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if idx != tc.wantIdx {
					t.Fatalf("expected index %d, got %d", tc.wantIdx, idx)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if idx != tc.wantIdx {
				t.Fatalf("expected index %d, got %d", tc.wantIdx, idx)
			}
		})
	}
}

func TestFloat64Data_Range(t *testing.T) {
	cases := []extremesCase{{
		name:    "empty",
		data:    []float64{},
		wantErr: ErrEmptyInput,
	}, {
		name:    "positive numbers",
		data:    []float64{1, 4, 2},
		wantVal: 3, // 4 - 1
		wantErr: nil,
	}, {
		name:    "negative numbers",
		data:    []float64{-5, -1, -3},
		wantVal: 4, // -1 - (-5)
		wantErr: nil,
	}, {
		name:    "mixed signs",
		data:    []float64{-2, 0, 5},
		wantVal: 7, // 5 - (-2)
		wantErr: nil,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.data).Range()
			if tc.wantErr != nil {
				if err == nil {
					t.Fatalf("expected error %v, got nil", tc.wantErr)
				}
				if err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.wantVal) > 1e-9 {
				t.Fatalf("expected range %v, got %v", tc.wantVal, got)
			}
		})
	}
}
